import re
import os
import pysftp
from onevizion import LogLevel, Trackor


class Module:

    def __init__(self, ov_module_log, sftp_data, trackor_data, module_service, module_helper):
        self._module_log = ov_module_log
        self._sftp_data = sftp_data
        self._trackor_data = trackor_data
        self._module_service = module_service
        self._module_helper = module_helper

    def start(self):
        self._module_log.add(LogLevel.INFO, 'Starting Module')

        sftp = self._sftp_data.connect()
        file_list = self._sftp_data.get_file_list(sftp)
        filter_file_list = self._module_helper.filter_files(file_list)
        self._module_log.add(LogLevel.INFO, f'{len(filter_file_list)} files found')

        for file_name in filter_file_list:
            fuze_id = self._module_helper.get_fuze_id(file_name)
            trackor_data = self._trackor_data.get_trackors(fuze_id)
            filter_trackors = self._module_helper.filter_trackors(trackor_data, fuze_id)
            self._module_log.add(LogLevel.INFO, f'{len(filter_trackors)} Trackors found for file "{file_name}"')
            if len(filter_trackors) > 0:
                self._module_service.process_file_data(sftp, file_name, filter_trackors)

        self._module_log.add(LogLevel.INFO, 'Module has been completed')


class ModuleService:

    def __init__(self, ov_module_log, module_helper, trackor_data, sftp_data):
        self._module_log = ov_module_log
        self._module_helper = module_helper
        self._trackor_data = trackor_data
        self._sftp_data = sftp_data

    def process_file_data(self, sftp, file_name, filter_trackors):
        self._sftp_data.download_file(sftp, file_name)
        is_file_exists = self._module_helper.check_file_exist(file_name)
        if is_file_exists:
            self._module_log.add(LogLevel.INFO, f'File "{file_name}" has been downloaded')

            for trackor in filter_trackors:
                self._trackor_data.upload_file(trackor, file_name)
                self._sftp_data.move_to_archive(sftp, file_name)
                self._module_log.add(LogLevel.INFO, f'File "{file_name}" has been uploaded and moved to the archive')

            self._module_helper.delete_file(file_name)
            is_file_exists = self._module_helper.check_file_exist(file_name)
            if is_file_exists is False:
                self._module_log.add(LogLevel.INFO, f'File "{file_name}" has been deleted')

        else:
            self._module_log.add(LogLevel.WARNING, f'File "{file_name}" has not been downloaded')


class ModuleHelper:

    def __init__(self, file_name_regexp_pattern):
        self._file_name_regexp_pattern = file_name_regexp_pattern

    def filter_files(self, file_list):
        compile_prefix = re.compile(self._file_name_regexp_pattern)
        filtered_files = list(filter(compile_prefix.search, file_list))

        return filtered_files

    def filter_trackors(self, trackor_data, fuze_id):
        filter_trackors = []
        for trackor in trackor_data:
            if trackor[TrackorData.FUZE_ID] == fuze_id:
                filter_trackors.append(trackor[TrackorData.TRACKOR_ID])

        return filter_trackors

    def get_fuze_id(self, file_name):
        fuze_id = re.search(r'\d+\.', file_name)
        if fuze_id is not None:
            fuze_id = fuze_id.group()[:-1]

        return fuze_id

    def check_file_exist(self, file_name):
        return os.path.exists(file_name)

    def delete_file(self, file_name):
        os.remove(file_name)


class ModuleError(Exception):
    pass


class TrackorData:
    TRACKOR_ID = 'TRACKOR_ID'
    PROJECT_STATUS = 'P_PROJECT_STATUS'
    FUZE_ID = 'P_FUZE_PROJECT_ID_FZ'
    EFILE_FIELD = 'P_MMUAT_FILE_SA'
    ACTIVE_STATUS = 'Active'

    def __init__(self, ov_url, ov_access_key, ov_secret_key):
        self._ov_trackor_type = Trackor(trackorType='Project', URL=ov_url, userName=ov_access_key,
                                        password=ov_secret_key, isTokenAuth=True)

    def get_trackors(self, fuze_id):
        self._ov_trackor_type.read(
            filters={TrackorData.PROJECT_STATUS: TrackorData.ACTIVE_STATUS,
                     TrackorData.FUZE_ID: fuze_id},
            fields={TrackorData.FUZE_ID}
        )

        if len(self._ov_trackor_type.errors) != 0:
            raise ModuleError(f'Failed to get_trackors: Exception [{self._ov_trackor_type.errors}]')

        return self._ov_trackor_type.jsonData

    def upload_file(self, trackor_id, file_name):
        self._ov_trackor_type.UploadFile(
            trackorId=trackor_id,
            fieldName=TrackorData.EFILE_FIELD,
            fileName=file_name
        )

        if len(self._ov_trackor_type.errors) != 0:
            raise ModuleError(f'Failed to upload_file for Trackor ID "{trackor_id}" for file "{file_name}": Exception [{self._ov_trackor_type.errors}]')

        return self._ov_trackor_type.jsonData


class SFTPData:

    def __init__(self, url, username, password, directory, archive):
        self._url = url
        self._username = username
        self._password = password
        self._directory = directory
        self._archive = archive

    
    def connect(self):
        cnopts = SFTPHelper(False, False, None, None)
        sftp = pysftp.Connection(host=self._url, username=self._username, password=self._password, cnopts = cnopts)

        return sftp

    def get_file_list(self, sftp):
        with sftp.cd(self._directory):
            file_list = sftp.listdir()

        return file_list

    def download_file(self, sftp, file_name):
        sftp.get(f'{self._directory}{file_name}', preserve_mtime=True)

    def move_to_archive(self, sftp, file_name):
        sftp.rename(f'{self._directory}{file_name}', f'{self._archive}{file_name}')


class SFTPHelper:

    def __init__(self, log, compression, ciphers, hostkeys):
        self.log = log
        self.compression = compression
        self.ciphers = ciphers
        self.hostkeys = hostkeys
