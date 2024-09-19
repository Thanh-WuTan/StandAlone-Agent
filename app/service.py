import zipfile
import os
import tempfile
import yaml
import pathlib
import json

PWD = os.path.dirname(__file__)
MYAGENT_DIR = os.path.join(PWD, '..', 'agent')

class StandaService:
    def __init__(self, services):
        self.services = services
        self.data_svc = services.get('data_svc')

    async def find_payload(self, payload_name):
        cwd = pathlib.Path.cwd()
        payload_dirs = [cwd / 'data' / 'payloads']
        payload_dirs.extend(cwd / 'plugins' / plugin.name / 'payloads'
                            for plugin in await self.data_svc.locate('plugins') if plugin.enabled)

        # Search for the payload file in the specified directories
        for payload_dir in payload_dirs:
            payload_path = payload_dir / payload_name
            if payload_path.exists() and payload_path.is_file():
                return payload_path
        return None

    async def create_tmp_dir(self):
        current_dir = os.path.dirname(__file__)
        tmp_parent_dir = os.path.join(current_dir, '..', 'tmp')
        temp_dir = tempfile.mkdtemp(dir=tmp_parent_dir)
        return temp_dir
    
    async def get_atomic_ordering(self, adversary_id):
        adversary = await self.data_svc.locate('adversaries', match=dict(adversary_id=adversary_id))
        if not adversary:
            return None
        profile = adversary[0].display
        atomic_ordering = profile['atomic_ordering']
        abilities = []
        for ability_id in atomic_ordering:
            ability = await self.data_svc.locate('abilities', match=dict(ability_id=ability_id))
            abilities.append(ability[0].display)
        return abilities

    async def create_abilities_dir(self, temp_dir, abilities):
        abilities_dir = os.path.join(temp_dir, 'abilities')
        os.makedirs(abilities_dir, exist_ok=True)
        for position, ability in enumerate(abilities, start=1):
            try:
                yml_filename = f'{position}.yml'
                yml_path = os.path.join(abilities_dir, yml_filename)
                with open(yml_path, 'w') as yml_file:
                    yaml.dump(ability, yml_file)
            except Exception as e:
                print(f"Error creating ability file for '{ability['name']}': {e}")
        return abilities_dir

    async def create_payloads_dir(self, temp_dir, abilities): 
        payloads_dir = os.path.join(temp_dir, 'payloads')
        os.makedirs(payloads_dir, exist_ok=True)
        
        payloads = set()
        for ability in abilities:
            for exc in ability['executors']:
                for payload in exc['payloads']:
                    payloads.add(payload)
        for payload in payloads:
            try: 
                payload_path = await self.find_payload(payload)
                if payload_path:
                    os.makedirs(payloads_dir, exist_ok=True)
                    payload_save_path = os.path.join(payloads_dir, payload)
                    with open(payload_save_path, 'wb') as dest_file:
                        with open(payload_path, 'rb') as src_file:
                            dest_file.write(src_file.read())
                else:
                    print(f"Payload '{payload}' not found.")
            except Exception as e:
                print(f"Error creating payload file for '{ability['name']}': {e}")

        # Create uuid_mapper file
        uuid_mapper_path = os.path.join(payloads_dir, 'uuid_mapper.json')
        with open(uuid_mapper_path, 'w') as uuid_mapper_file:
            uuid_mapper = self.services.get('file_svc').get_payloads()
            json.dump(uuid_mapper, uuid_mapper_file, indent=4)
        return payloads_dir
    
    async def create_parsers_dir(self, temp_dir, abilities):
        parsers_dir = os.path.join(temp_dir, 'parsers')
        os.makedirs(parsers_dir, exist_ok=True)
        for ability in abilities:
            for exc in ability['executors']:
                for parser in exc['parsers']:
                    module = parser['module'].split('.')
                    plugin = module[1]
                    parser_name = module[-1] + '.py'
                    os.makedirs(os.path.join(parsers_dir, plugin), exist_ok=True)
                    await self.copy_file(os.path.join(PWD, 'parsers', plugin, parser_name),
                                   os.path.join(parsers_dir, plugin, parser_name))
        return parsers_dir
    
    async def copy_file(self, source, destination):
        try:
            with open(destination, 'wb') as dest_file:
                with open(source, 'rb') as src_file:
                    dest_file.write(src_file.read())
        except Exception as e:
            print(f"Error copying {source}: {e}")
        return destination
    
    async def copy_folder(self, temp_dir, target):
        destination_dir = os.path.join(temp_dir, target)
        os.makedirs(destination_dir, exist_ok=True)

        source_dir = os.path.join(MYAGENT_DIR, target) 
        for file_name in os.listdir(source_dir):
            source_file = os.path.join(source_dir, file_name)
            destination_file = os.path.join(destination_dir, file_name)
            if os.path.isfile(source_file):
                await self.copy_file(source_file, destination_file)
        return destination_dir

    async def download_standalone_agent(self, adversary_id):
        temp_dir = await self.create_tmp_dir()
        abilities = await self.get_atomic_ordering(adversary_id)
        abilities_dir = await self.create_abilities_dir(temp_dir, abilities)
        payloads_dir = await self.create_payloads_dir(temp_dir, abilities)
        parsers_dir = await self.create_parsers_dir(temp_dir, abilities)
        objects_dir = await self.copy_folder(temp_dir, 'objects')
        learning_dir = await self.copy_folder(temp_dir, 'learning')
        sources_dir = await self.copy_folder(temp_dir, 'sources')
        
        main_agent_file = await self.copy_file(os.path.join(MYAGENT_DIR, 'main.py'), os.path.join(temp_dir, 'main.py'))

        with open(main_agent_file, 'r') as f:
            content = f.read() 
        content = content.replace("ADV_ID = 'adversary_id'", f"ADV_ID = '{adversary_id}'")
        with open(main_agent_file, 'w') as f:
            f.write(content)

        directories = [abilities_dir, payloads_dir, objects_dir, parsers_dir, learning_dir, sources_dir]
        
        # Create the zip file
        zip_path = os.path.join(temp_dir, adversary_id + ".zip")
             
        with zipfile.ZipFile(zip_path, 'w') as zip_file:
            for dir in directories:
                for root, _, files in os.walk(dir):
                    for file in files:
                        zip_file.write(os.path.join(root, file), arcname=os.path.relpath(os.path.join(root, file), temp_dir))
            zip_file.write(main_agent_file, arcname=os.path.relpath(main_agent_file, temp_dir))
        return zip_path
