import argparse
import ConfigParser
import os
import subprocess
import sys
import urllib2
import zlib

try:
    import simplejson as json
except ImportError:
    import json

from gondor import __version__
from gondor import http, utils


def cmd_init(args, config):
    gondor_dir = os.path.join(os.getcwd(), ".gondor")
    if not os.path.exists(gondor_dir):
        os.mkdir(gondor_dir)
        if True: # @@@ allow turning off the auto commit
            if os.path.join(os.getcwd(), ".git"):
                # git add .gondor
                # git commit -m "gondor init"
                pass
            if os.path.join(os.getcwd(), ".hg"):
                # whatever the heck the equivlent is in hg
                pass


def cmd_deploy(args, config):
    label = args.domain[0]
    commit = args.commit[0]
    
    gondor_dirname = ".gondor"
    repo_root = utils.find_nearest(os.cwd(), gondor_dirname)
    tarball = None
    
    try:
        sys.stdout.write("Reading configuration... ")
        config = ConfigParser.RawConfigParser()
        config.read(os.path.join(repo_root, gondor_dirname))
        client_key = config.get("gondor", "client_key")
        sys.stdout.write("[ok]\n")
        
        sys.stdout.write("Building tarball from %s... " % commit)
        tarball = os.path.abspath(os.path.join(repo_root, "%s.tar.gz" % domain))
        cmd = "(cd %s && git archive --format=tar %s | gzip > %s)" % (repo_root, commit, tarball)
        subprocess.call([cmd], shell=True)
        sys.stdout.write("[ok]\n")
        
        text = "Pushing tarball to Gondor... "
        sys.stdout.write(text)
        url = "http://gondor.eldarion.com/deploy/"
        mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, url, config["username"], config["password"])
        opener = urllib2.build_opener(
            urllib2.HTTPBasicAuthHandler(mgr),
            http.MultipartPostHandler,
            http.UploadProgressHandler
        )
        params = {
            "client_key": client_key,
            "label": label,
            "tarball": open(tarball, "rb"),
        }
        response = opener.open(url, params)
        data = json.loads(response.read())
        if data["status"] == "error":
            message = data["message"]
        elif data["status"] == "success":
            message = "ok"
        else:
            message = "unknown"
        sys.stdout.write("\r%s[%s]   \n" % (text, message))
    finally:
        if tarball:
            os.unlink(tarball)


def cmd_sqldump(args, config):
    domain = args.domain[0]
    
    # request SQL dump and stream the response through uncompression
    
    d = zlib.decompressobj(16+zlib.MAX_WBITS)
    sql_url = "http://gondor.eldarion.com/sqldump/%s" % domain
    mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, sql_url, config["username"], config["password"])
    opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(mgr))
    response = opener.open(sql_url)
    cs = 16 * 1024
    while True:
        chunk = response.read(cs)
        if not chunk:
            break
        sys.stdout.write(d.decompress(chunk))
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(prog="gondor")
    parser.add_argument("--version", action="version", version="%%(prog)s %s" % __version__)
    
    command_parsers = parser.add_subparsers(dest="command")
    
    # cmd: init
    parser_init = command_parsers.add_parser("init")
    parser_init.add_argument("client_key", nargs=1)
    
    # cmd: deploy
    parser_deploy = command_parsers.add_parser("deploy")
    parser_deploy.add_argument("label", nargs=1)
    parser_deploy.add_argument("commit", nargs=1)
    
    # cmd: sqldump
    parser_sqldump = command_parsers.add_parser("sqldump")
    parser_sqldump.add_argument("domain", nargs=1)
    
    args = parser.parse_args()
    
    # config
    
    config = ConfigParser.RawConfigParser()
    config.read(os.path.expanduser("~/.gondor"))
    config = {
        "username": config.get("auth", "username"),
        "password": config.get("auth", "password"),
    }
    
    {
        "init": cmd_init,
        "deploy": cmd_deploy,
        "sqldump": cmd_sqldump
    }[args.command](args, config)
