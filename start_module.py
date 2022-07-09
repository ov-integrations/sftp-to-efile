import sys
import subprocess

subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'python_dependencies.txt'])

import json
import re
from jsonschema import validate
from onevizion import IntegrationLog, LogLevel
from module import SFTPData, TrackorData, Module, ModuleError


with open('settings.json', 'rb') as PFile:
    settings_data = json.loads(PFile.read().decode('utf-8'))

with open('settings_schema.json', 'rb') as PFile:
    data_schema = json.loads(PFile.read().decode('utf-8'))

try:
    validate(instance = settings_data, schema = data_schema)
except Exception as e:
    raise Exception(f'Incorrect value in the settings file\n{str(e)}')

sftp_url = settings_data['sftpUrl']
sftp_username = settings_data['sftpUserName']
sftp_password = settings_data['sftpPassword']
sftp_directory = settings_data['sftpDirectory']
sftp_directory_archive = settings_data['sftpDirectoryArchive']
sftp_file_name_regexp_pattern = settings_data['sftpFileNameRegexpPattern']
sftp_fuze_id_regexp_pattern = settings_data['sftpFuzeIdRegexpPattern']

ov_url = re.sub('^http://|^https://', '', settings_data['ovUrl'][:-1])
ov_access_key = settings_data['ovAccessKey']
ov_secret_key = settings_data['ovSecretKey']


with open('ihub_parameters.json', 'rb') as PFile:
    module_data = json.loads(PFile.read().decode('utf-8'))

process_id = module_data['processId']
log_level = module_data['logLevel']

module_log = IntegrationLog(process_id, ov_url, ov_access_key, ov_secret_key, None, True, log_level)
sftp_data = SFTPData(sftp_url, sftp_username, sftp_password, sftp_directory, sftp_directory_archive)
trackor_data = TrackorData(ov_url, ov_access_key, ov_secret_key)
module = Module(module_log, sftp_data, trackor_data, sftp_file_name_regexp_pattern, sftp_fuze_id_regexp_pattern)

try:
    module.start()
except ModuleError as module_error:
    module_log.add(LogLevel.ERROR, str(module_error))
    raise module_error
