import re
import os
from pysftp import Connection
from onevizion import LogLevel, IntegrationLog, Trackor


class Module:

    def __init__(self, ov_module_log: IntegrationLog, ov_url: str, settings_data: list) -> None:
        self._module_log = ov_module_log
        self._sftp_data = SFTPData(settings_data)
        self._trackor_data = TrackorData(ov_url, settings_data)
        self._file_name_regexp_pattern = settings_data['sftpFileNameRegexpPattern']
        self._fuze_id_regexp_pattern = settings_data['sftpFuzeIdRegexpPattern']

    def start(self):
        self._module_log.add(LogLevel.INFO, 'Starting Module')

        with self._sftp_data.connect() as sftp:
            file_list = self._sftp_data.get_file_list(sftp)
            filtered_file_list = ModuleService.filter_files(file_list, self._file_name_regexp_pattern)
            self._module_log.add(LogLevel.INFO, f'{len(filtered_file_list)} files found')

            for file_name in filtered_file_list:
                fuze_id = ModuleService.get_fuze_id(file_name, self._fuze_id_regexp_pattern)
                trackor_data = self._trackor_data.get_trackors(fuze_id)
                filtered_trackors = ModuleService.filter_trackors(trackor_data, fuze_id)
                self._module_log.add(LogLevel.INFO, f'{len(filtered_trackors)} Trackors found for file "{file_name}"')
                if len(filtered_trackors) > 0:
                    ModuleService.process_file_data(sftp, file_name, filtered_trackors, self._module_log,
                                                    self._sftp_data, self._trackor_data)

        self._module_log.add(LogLevel.INFO, 'Module has been completed')


class TrackorData:
    TRACKOR_ID = 'TRACKOR_ID'
    PROJECT_STATUS = 'P_PROJECT_STATUS'
    FUZE_ID = 'P_FUZE_PROJECT_ID_FZ'
    EFILE_FIELD = 'P_MMUAT_FILE_SA'
    ACTIVE_STATUS = 'Active'

    def __init__(self, ov_url: str, settings_data: list) -> None:
        self._ov_trackor_type = Trackor(trackorType='Project', URL=ov_url, userName=settings_data['ovAccessKey'],
                                        password=settings_data['ovSecretKey'], isTokenAuth=True)

    def get_trackors(self, fuze_id: str) -> list:
        self._ov_trackor_type.read(
            filters={TrackorData.PROJECT_STATUS: TrackorData.ACTIVE_STATUS,
                     TrackorData.FUZE_ID: fuze_id},
            fields={TrackorData.FUZE_ID}
        )

        if len(self._ov_trackor_type.errors) == 0:
            return self._ov_trackor_type.jsonData

        raise ModuleError('Failed to get_trackors', self._ov_trackor_type.errors)

    def upload_file(self, trackor_id: int, file_name: str) -> list:
        self._ov_trackor_type.UploadFile(
            trackorId=trackor_id,
            fieldName=TrackorData.EFILE_FIELD,
            fileName=file_name
        )

        if len(self._ov_trackor_type.errors) == 0:
            return self._ov_trackor_type.jsonData

        raise ModuleError(f'Failed to upload_file for Trackor ID "{trackor_id}" for file "{file_name}"',
                          self._ov_trackor_type.errors)


class SFTPData:

    def __init__(self, settings_data: list) -> None:
        self._url = settings_data['sftpUrl']
        self._username = settings_data['sftpUserName']
        self._password = settings_data['sftpPassword']
        self._directory = settings_data['sftpDirectory']
        self._archive = settings_data['sftpDirectoryArchive']
        self._cnopts = SFTPHelper()

    def connect(self) -> Connection:
        try:
            return Connection(host=self._url, username=self._username,
                              password=self._password, cnopts=self._cnopts)
        except Exception as exception:
            raise ModuleError('Failed to connect', exception) from exception

    def get_file_list(self, sftp: Connection) -> list:
        try:
            with sftp.cd(self._directory):
                file_list = sftp.listdir()
        except Exception as exception:
            raise ModuleError('Failed to get_file_list', exception) from exception

        return file_list

    def download_file(self, sftp: Connection, file_name: str) -> None:
        try:
            sftp.get(f'{self._directory}{file_name}', preserve_mtime=True)
        except Exception as exception:
            raise ModuleError('Failed to download_file', exception) from exception

    def move_to_archive(self, sftp: Connection, file_name: str) -> None:
        try:
            sftp.rename(f'{self._directory}{file_name}', f'{self._archive}{file_name}')
        except Exception as exception:
            raise ModuleError('Failed to move_to_archive', exception) from exception


class SFTPHelper:

    def __init__(self, log=False, compression=False, ciphers=None, hostkeys=None):
        self.log = log
        self.compression = compression
        self.ciphers = ciphers
        self.hostkeys = hostkeys


class ModuleService:

    @staticmethod
    def process_file_data(sftp, file_name: str, filtered_trackors: list, ov_module_log: IntegrationLog,
                          sftp_data: SFTPData, trackor_data: TrackorData) -> None:
        sftp_data.download_file(sftp, file_name)
        is_file_exists = os.path.exists(file_name)
        if is_file_exists:
            ov_module_log.add(LogLevel.DEBUG, f'File "{file_name}" has been downloaded')

            for trackor in filtered_trackors:
                trackor_data.upload_file(trackor, file_name)

            sftp_data.move_to_archive(sftp, file_name)
            ov_module_log.add(LogLevel.INFO, f'File "{file_name}" has been uploaded and moved to the archive')

            os.remove(file_name)
            ov_module_log.add(LogLevel.DEBUG, f'File "{file_name}" has been deleted')

        else:
            ov_module_log.add(LogLevel.WARNING, f'File "{file_name}" has not been downloaded')

    @staticmethod
    def filter_files(file_list: list, file_name_regexp_pattern: str) -> list:
        compile_prefix = re.compile(file_name_regexp_pattern)
        filtered_files = list(filter(compile_prefix.search, file_list))

        return filtered_files

    @staticmethod
    def filter_trackors(trackor_data: list, fuze_id: str) -> list:
        filtered_trackors = []
        for trackor in trackor_data:
            if trackor[TrackorData.FUZE_ID] == fuze_id:
                filtered_trackors.append(trackor[TrackorData.TRACKOR_ID])

        return filtered_trackors

    @staticmethod
    def get_fuze_id(file_name: str, fuze_id_regexp_pattern: str) -> str:
        fuze_id = re.search(fuze_id_regexp_pattern, file_name)
        if fuze_id is not None:
            fuze_id = fuze_id.group()[:-1]

        return fuze_id


class ModuleError(Exception):

    def __init__(self, error_message: str, description) -> None:
        self._message = error_message
        self._description = description

    @property
    def message(self) -> str:
        return self._message

    @property
    def description(self) -> str:
        return self._description
