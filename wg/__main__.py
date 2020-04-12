from jinja2 import Environment, FileSystemLoader, select_autoescape
from os import chdir, listdir, path, unlink, rename, system, mkdir, stat
from yaml import safe_load as yaml_load, dump as yaml_dump

__dir__ = path.abspath(path.dirname(__file__))
chdir(__dir__)

config = None
with open(path.join(__dir__, '../config.yml'), 'r') as f:
    config = yaml_load(f)

INTERFACEDIR = path.join(__dir__, 'interfaces')

def swapFile(fn, content):
    newfile = '%s.new' % fn
    fh = open(newfile, 'w')
    fh.write(content)
    fh.close()

    try:
        fh = open(fn, 'r')
        oldcontent = fh.read()
        fh.close()
        if oldcontent == content:
            print('<%s> Old == New' % fn)
            unlink(newfile)
            return False

        unlink(fn)
    except FileNotFoundError:
        pass

    print('<%s> Old != New' % fn)
    rename(newfile, fn)

    return True

def loadInterface(name):
    fn = path.join(INTERFACEDIR, name)
    fh = open(fn, 'r')
    data = fh.read()
    fh.close()
    return yaml_load(data)

j2env = Environment(
    loader=FileSystemLoader(path.join(__dir__, 'templates')),
    autoescape=select_autoescape([])
)

wgInterfaceTemplate = j2env.get_template('wg.conf.j2')

fh = open('/etc/wireguard/keys/private', 'r')
privateKey = fh.read()
fh.close()

for fn in listdir(INTERFACEDIR):
    if fn[0] == '.' or fn[-4:] != '.yml':
        continue
    ifName = fn[:-4]

    iface = loadInterface(fn)

    confName = '/etc/wireguard/%s.conf' % ifName
    srvName = 'wg-quick@%s' % ifName

    wgConfig = wgInterfaceTemplate.render(config=iface, privateKey=privateKey, serverId=config['serverId'])

    system('systemctl enable %s' % srvName)
    if swapFile(confName, wgConfig):
        system('systemctl restart %s' % srvName)
