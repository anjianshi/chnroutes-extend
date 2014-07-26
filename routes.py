#-*- coding: utf-8 -*-
"""
VPN routes 管理脚本（仅支持 Windows）
通过此脚本管理要跳过不走 VPN 的 IP

routes 分两种：
  chnroutes       包含所有中国 IP，存放于 chnroutes.txt，格式：IP mask
  custom_routes   是一些不想走 VPN 的外国 IP，
                  存放于 custom_routes.txt，格式：IP domain/ip


参数：
up      启用 routes（相当于 vpnup.dat）
down    停用 routes（相当于 vpndown.dat）
---
gen     重新生成 chnroutes
---
add domain/ip       添加一条 custom_routes，并立即将它启用
del domain/ip       删除某条 custom_routes，并立即将它禁用
"""

import os
import sys
import urllib2
import re
import math
import socket
import subprocess


def up(only_custom=False):
  routes = get_all_routes() if not only_custom else get_custom_routes()
  cmd_list = [
    'for /F "tokens=3" %%* in (\'route print ^| findstr "\\<0.0.0.0\\>"\') do set "gw=%%*"',
    'ipconfig /flushdns'
  ]
  for route in routes:
    cmd_list.append('route add {} mask {} %gw% metric {}'.format(*route))
  run_cmd(cmd_list)


def down(only_custom=False):
  routes = get_all_routes() if not only_custom else get_custom_routes()
  run_cmd(['route delete ' + route[0] for route in routes])


def gen():
  if os.path.isfile("chnroutes.txt"):
    down()
    os.remove('chnroutes.txt')

  with open('chnroutes.txt', 'w') as f:
    for starting_ip, mask, _ in fetch_ip_data():
      f.write(starting_ip + " " + mask + "\n")

  print "\ncomplete"



# helper func

def fetch_ip_data():
    """取得中国区的 IP
    此函数取自 chnroutes.py"""
    #fetch data from apnic
    print "Fetching data from apnic.net, it might take a few minutes, please wait..."
    url=r'http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest'
    data=urllib2.urlopen(url).read()
    
    cnregex=re.compile(r'apnic\|cn\|ipv4\|[0-9\.]+\|[0-9]+\|[0-9]+\|a.*',re.IGNORECASE)
    cndata=cnregex.findall(data)
    
    results=[]

    for item in cndata:
        unit_items=item.split('|')
        starting_ip=unit_items[3]
        num_ip=int(unit_items[4])
        
        imask=0xffffffff^(num_ip-1)
        #convert to string
        imask=hex(imask)[2:]
        mask=[0]*4
        mask[0]=imask[0:2]
        mask[1]=imask[2:4]
        mask[2]=imask[4:6]
        mask[3]=imask[6:8]
        
        #convert str to int
        mask=[ int(i,16 ) for i in mask]
        mask="%d.%d.%d.%d"%tuple(mask)
        
        #mask in *nix format
        mask2=32-int(math.log(num_ip,2))
        
        results.append((starting_ip,mask,mask2))
         
    return results


def get_all_routes():
  """return ip, mask, metric"""
  routes = _get_chnroutes()
  routes.extend(_get_custom_routes())
  return routes


def get_chnroutes():
  """取出 chnroutes 列表
  return ip, mask, metric"""
  if not os.path.isfile("chnroutes.txt"):
    return []
  else:
    with open('chnroutes.txt') as f:
      routes = []
      for route in f:
        route = route.replace("\r", "").replace("\n", "").split(" ")
        routes.append([route[0], route[1], '25'])
      return routes


def get_custom_routes():
  """生成 custom_routes 列表
  return ip, mask, metric"""
  return [[get_ip(source), '255.255.255.255', '25'] for source in read_custom_routes_txt()]


def read_custom_routes_txt():
  """读取 custom_routes.txt，返回 source 列表
  （source 既可能是 domain 也可能是 ip）"""
  if not os.path.isfile("custom_routes.txt"):
    return []
  else:
    with open('custom_routes.txt') as f:
      # strip() 方法既能清除换行符，又能清除字符串两侧的空格和制表符
      return [source.strip(' \t\n\r') for source in f]


def get_ip(domain_or_ip):
  if re.match('^\d+\.\d+\.\d+\.\d+$', domain_or_ip):
    return domain_or_ip
  else:
    try:
      return socket.getaddrinfo(domain_or_ip,'http')[0][4][0]
    except socket.gaierror:
      print (u'notice: 找不到指定的域名(' + unicode(domain_or_ip) + u')对应的 IP 地址').encode('gbk')
      return False


_FNULL = open(os.devnull, 'w')


def run_cmd(cmd_list):
  """把给出的 command 列表写入一个临时的批处理文件，并执行"""
  cmd_list.insert(0, '@echo off')
  cmd_txt = "\n".join(cmd_list)

  with open('temp_cmd.bat', 'w') as f:
    f.write(cmd_txt)

  print 'handling...'
  subprocess.call('temp_cmd.bat', stdout=_FNULL, stderr=subprocess.STDOUT)
  os.remove('temp_cmd.bat')
  print 'complate'


def print_doc():
  print __doc__.decode('utf-8').encode('gbk')


# cli
if __name__ == '__main__':
  arg_len = len(sys.argv) - 1

  if arg_len == 0:
    print_doc()

  elif sys.argv[1] == 'up':
    up()

  elif sys.argv[1] == 'down':
    down()

  elif sys.argv[1] == 'gen':
    gen()

  elif sys.argv[1] == 'add' and len(sys.argv) == 3:
    new_source = sys.argv[2].strip(" \t\r\n")
    
    # 检查能否获取到域名对应的 ip (即使获取不到也不会终止操作)
    get_ip(new_source)

    sources = read_custom_routes_txt()

    if new_source not in sources:
      sources.append(new_source)

      with open('custom_routes.txt', 'w') as f:
        f.write("\n".join(sources))

      down(only_custom=True)
      up(only_custom=True)

  elif sys.argv[1] == 'del' and len(sys.argv) == 3:
    target_source = sys.argv[2].strip(" \t\r\n")
    sources = read_custom_routes_txt()
    if target_source in sources:
      sources.remove(target_source)

      with open('custom_routes.txt', 'w') as f:
        f.write("\n".join(sources))

      down(only_custom=True)
    else:
      print (u'custom routes 里没有此对象(' + unicode(target_source) + u')').encode('gbk')

  else:
    print_doc()