dns_dnssec = true

-- BEGIN STAGE 1 AUTOCONFIG
local site_records_a = {
{%- for ip in dynConfig._find('siteips4')|sort %}
    '{{ ip }}',
{%- endfor %}
}

local site_records_aaaa = {
{%- for ip in dynConfig._find('siteips6')|sort %}
    '{{ ip }}',
{%- endfor %}
}

local site_record_cname = '{{ dynConfig._find('sitecname') }}.'

local site_records_vanity_ns = {
{%- for rName, rValue in dynConfig._find('vanityNSRecords')|dictsort %}
    { name = '{{ rName }}', type = 'A', value = '{{ rValue.ip4 }}' },
    { name = '{{ rName }}', type = 'AAAA', value = '{{ rValue.ip6 }}' },
    { name = '@', type = 'NS', value = '{{ rName }}' },
{%- endfor %}
}


local site_records_default_ns = {
{%- for ns in dynConfig._find('nsrecords')|sort %}
    '{{ ns }}.',
{%- endfor %}
}

local site_records_google_mx = {
    { type = 'MX', value = '5 alt2.aspmx.l.google.com.' },
    { type = 'MX', value = '5 alt1.aspmx.l.google.com.' },
    { type = 'MX', value = '1 aspmx.l.google.com.' },
    { type = 'MX', value = '10 aspmx3.googlemail.com.' },
    { type = 'MX', value = '10 aspmx2.googlemail.com.' },
    { type = 'TXT', value = 'v=spf1 include:_spf.google.com mx ~all' },
}

local dnssec_dir = '{{ dynConfig._self.dnssecDir }}'
-- END STAGE 1 AUTOCONFIG

local root_domains = {}
local root_domain_meta = {}
local records_meta = {}
local records = {}

local function get_domain_id(qname)
    local meta = records_meta[qname:toString()]
    if meta then
        return meta.domain_id
    end
    return -1
end

function dns_lookup(qtype, qname, d_id, ctx)
    local qtype_name = qtype:getName()
    local rr = records[qname:toString()]
    if not rr then
        return {}
    end

    if qtype_name == "ANY" then
        local res = {}
        for _, recs in pairs(rr) do
            for _, rec in ipairs(recs) do
                table.insert(res, rec)
            end
        end
        return res
    end

    local res = rr[qtype_name]
    if not res then
        return {}
    end

    return res
end

function dns_list(qname, id)
    if id == -1 then
        id = get_domain_id(qname)
        if id == -1 then
            return false
        end
    end
    qname = root_domains[id]

    ret = {}

    for _, name in pairs(root_domain_meta[qname].records) do
        local rr = records[name]
        for _, v in pairs(rr) do
            for idx, row in ipairs(v) do
                table.insert(ret, row)
            end
        end
    end

    return ret
end

function dns_get_domaininfo(dom)
    local meta = root_domain_meta[dom:toString()]
    if meta then
        return meta.info
    end
    return false
end

function dns_get_domain_metadata(dom, kind)
    return false
end

function dns_get_domain_keys(dom)
    local meta = root_domain_meta[dom:toString()]
    if meta then
        return meta.dnssec
    end
    return false
end

function dns_get_before_and_after_names_absolute(did, qname)
    if did == -1 then
        did = get_domain_id(qname)
        if did == -1 then
            return {}
        end
    end

    local base_str = root_domains[did]
    local base = newDN(base_str)
    -- find out before and after name
    local before = newDN("")
    local after = newDN("")
    local empty = newDN("")

    for i, rr in ipairs(root_domain_meta[base_str].records) do               
        rr = rr:makeRelative(base)
        if qname:canonCompare(rr) == false then
            if before == empty then
                before = rr
            end
        else
            if after == empty then
                after = rr
            end
        end
    end

    return { unhashed=qname,before=before,after=after }
end

local last_zone

local function ensure_dot(name)
    if name:sub(-1) == '.' then
        return name
    end
    return name .. '.'
end

local function add_zone(zone, serial)
    zone = ensure_dot(zone)

    table.insert(root_domains, zone)
    last_zone = zone
    root_domain_meta[zone] = {
        records = {},
        dnssec = {},
        info = {
            id = #root_domains,
            serial = serial,
        },
    }
end

local function get_upper_domain_id(qname)
    for id, dom in ipairs(root_domains) do
        if qname:toString() == dom or qname:isPartOf(newDN(dom)) then
            return id
        end
    end
    return -1
 end

local function add_record(name, rType, rContent, rTTL)
    name = ensure_dot(name)

    local name_records = records[name]
    if not name_records then
        local domain_id = get_upper_domain_id(newDN(name))
        name_records = {}
        records_meta[name] = {
            domain_id = domain_id,
        }
        table.insert(root_domain_meta[root_domains[domain_id]].records, name)
        records[name] = name_records
    end

    local type_records = name_records[rType]
    if not type_records then
        type_records = {}
        name_records[rType] = type_records
    end

    table.insert(type_records, {
        domain_id = records_meta[name].domain_id,
        name = name,
        ttl = rTTL or 300,
        type = newQType(rType),
        content = rContent,
    })
end

local function add_record_prepend(name, rType, rContent, rTTL)
    if name == '@' then
        name = last_zone
    else
        name = name .. '.' .. last_zone
    end
    return add_record(name, rType, rContent, rTTL)
end

local function add_google_mx()
    for _, rec in ipairs(site_records_google_mx) do
        add_record_prepend('@', rec.type, rec.value, 3600)
    end
end

local function add_vanity_ns()
    for _, rec in ipairs(site_records_vanity_ns) do
        add_record_prepend(rec.name, rec.type, rec.value, 3600)
    end
end

local function add_default_ns()
    for _, rec in ipairs(site_records_default_ns) do
        add_record_prepend('@', 'NS', rec, 3600)
    end
end

local function add_domain_siteip(name)
    name = ensure_dot(name)

    if root_domain_meta[name] or name == site_record_cname then
        for _, rec in ipairs(site_records_a) do
            add_record(name, 'A', rec)
        end
        for _, rec in ipairs(site_records_aaaa) do
            add_record(name, 'AAAA', rec)
        end
        return
    end
    add_record(name, 'CNAME', site_record_cname)
end

-- BEGIN STAGE 2 AUTOCONFIG
{%- for mainDomain, zone in zones|dictsort %}
    {%- set site = zone.site %}
    {%- set mainDomainStripLen = -((mainDomain | length) + 1) %}

add_zone('{{ mainDomain }}', {{ zone.serial | int }})

add_record_prepend('@', 'SOA', '{{ zone.name }}. root.{{ zone.name }}. {{ zone.serial | int }} 3600 900 604800 3600', 3600)

    {%- if site.vanityNS %}
add_vanity_ns()
    {%- else %}
add_default_ns()
    {%- endif %}

    {%- if site.type != 'none' %}
        {%- for domain in zone.domains|sort %}
add_domain_siteip('{{ domain }}')
        {%- endfor %}
    {%- endif %}

    {%- for record in site.records|sort(attribute='name') %}
add_record_prepend('{{ record.name }}', '{{ record.type }}', '{{ record.value }}', {{ record.ttl | default(300) | int}})
    {%- endfor %}

    {%- if site.useGoogleMX %}
add_google_mx()
    {%- endif %}
{%- endfor %}
-- END STAGE 2 AUTOCONFIG

local function record_compare(a, b)
    return newDN(a):canonCompare(newDN(b))
end

for _, v in pairs(root_domain_meta) do
    table.sort(v.records, record_compare)
end

local function read_dnssec_file(file)
    local fh = io.open(dnssec_dir .. '/' .. file)
    if not fh then
        return
    end
    contents = fh:read('*a')
    fh:close()
    return contents
end

local function add_keys(zone, alg, id)
    local fname = 'K' .. zone .. '+' .. alg .. '+' .. id

    local key_data = read_dnssec_file(fname .. '.key')
    if not key_data then
        return
    end
    local key_flags = key_data:match(zone .. ' IN DNSKEY (%d+) ')
    if not key_flags then
        return
    end

    local content = read_dnssec_file(fname .. '.private')
    if not content then
        return
    end

    local meta = root_domain_meta[zone]
    if not meta then
        return
    end

    table.insert(meta.dnssec, {
        content = content,
        flags = key_flags,
    })
end

local p = io.popen('find "' .. dnssec_dir .. '" -type f')
for file in p:lines() do
    local zone, alg, id, typ = file:match('/K([a-z0-9.-]+)%+(%d+)%+(%d+).(%w+)$')
    if typ == "key" then
        add_keys(zone, alg, id)
    end
end
