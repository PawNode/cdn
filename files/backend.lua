dns_dnssec = true

print("PawNode CDN Lua DNSSEC loading...")

local dnssec_dir = '/etc/powerdns/dnssec'

local dnssec_data = {}

local function read_dnssec_file(file)
    local fh = io.open(dnssec_dir .. '/' .. file)
    if not fh then
        return
    end
    local contents = fh:read('*a')
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

    if not dnssec_data[zone] then
        dnssec_data[zone] = {}
    end

    table.insert(dnssec_data[zone], {
        content = content,
        flags = key_flags,
    })
end

local function scan_dnssec()
    dnssec_data = {}
    local p = io.popen('find "' .. dnssec_dir .. '" -type f')
    for file in p:lines() do
        local zone, alg, id, typ = file:match('/K([a-z0-9.-]+)%+(%d+)%+(%d+).(%w+)$')
        if typ == "key" then
            add_keys(zone, alg, id)
        end
    end
end

function dns_lookup()
    return {}
end

function dns_get_domain_metadata()
    return false
end

function dns_get_before_and_after_names_absolute()
    return false
end

function dns_get_domain_keys(dom)
    dom = dom:toString()
    print("Loading DNSSEC keys for", dom)
    return dnssec_data[dom] or false
end

scan_dnssec()
