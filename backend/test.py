import os 
import docker
import struct

os.environ["DOCKER_HOST"] = "tcp://192.168.220.129:2375"


client = docker.from_env()
container = client.containers.get('37eb05b0245aec155a89c2b1fde73639661fc06360b8a118befd4985a7fdd52f')

options = {
    'stdout': True,
    'stderr': True,
    'timestamps': False,
    'stream': False,
    'follow': False,
    'tail': 100,  # 只读最后 100 行
}


container.logs(**options)