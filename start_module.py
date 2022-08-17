import sys
import subprocess

subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'python_dependencies.txt'])

import json
import re
from jsonschema import validate
from onevizion import IntegrationLog, LogLevel
from module import Module, ModuleError


with open('fill_settings.json', 'rb') as PFile:
    settings_data = json.loads(PFile.read().decode('utf-8'))

with open('settings_schema.json', 'rb') as PFile:
    data_schema = json.loads(PFile.read().decode('utf-8'))

try:
    validate(instance = settings_data, schema = data_schema)
except Exception as exceptiion:
    raise Exception(f'Incorrect value in the settings file\n{str(exceptiion)}') from exceptiion

ov_url = re.sub('^http://|^https://', '', settings_data['ovUrl'][:-1])
ov_access_key = settings_data['ovAccessKey']
ov_secret_key = settings_data['ovSecretKey']

with open('ihub_parameters.json', 'rb') as PFile:
    module_data = json.loads(PFile.read().decode('utf-8'))

process_id = module_data['processId']
log_level = module_data['logLevel']

module_log = IntegrationLog(process_id, ov_url, ov_access_key, ov_secret_key, None, True, log_level)
module = Module(module_log, ov_url, settings_data)

try:
    module.start()
except ModuleError as module_error:
    module_log.add(LogLevel.ERROR, str(module_error.message), str(module_error.description))
    raise module_error
