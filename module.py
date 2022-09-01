import re
import os
from pysftp import Connection
from onevizion import LogLevel, IntegrationLog, Trackor


class Module:

    def __init__(self, ov_module_log: IntegrationLog, ov_url: str, settings_data: dict) -> None:
        self._module_log = ov_module_log
        self._sftp_service = SFTPService(settings_data)
        self._trackor_service = TrackorService(ov_url, settings_data)
        self._settings_data = settings_data

    def start(self):
        self._module_log.add(LogLevel.INFO, 'Starting Module')

        with self._sftp_service.connect() as sftp:
            file_list = self._sftp_service.get_file_list(sftp)
            for sftp_file_to_ov_mapping in self._settings_data['sftpFileToOvMappings']:
                trackor_type = sftp_file_to_ov_mapping['ovTrackorType']
                regexp_pattern = sftp_file_to_ov_mapping['sftpFileNameRegexp']
                filtered_file_list = self._filter_files(file_list, regexp_pattern)
                self._module_log.add(LogLevel.INFO, f'{len(filtered_file_list)} files found for the regexp pattern "{regexp_pattern}"')

                for file_name in filtered_file_list:
                    trackor_filter = sftp_file_to_ov_mapping['ovTrackorFilter']
                    search_conditions = self._get_search_conditions(trackor_filter, file_name)
                    trackor_data = self._trackor_service.get_trackors(trackor_type, search_conditions)
                    self._module_log.add(LogLevel.INFO, f'{len(trackor_data)} Trackors found for the file "{file_name}"')
                    if len(trackor_data) > 0:
                        self._process_file_data(sftp, sftp_file_to_ov_mapping['ovEfileFieldName'], file_name,
                            trackor_data, trackor_type)

        self._module_log.add(LogLevel.INFO, 'Module has been completed')

    def _filter_files(self, file_list: list, file_name_regexp_pattern: str) -> list:
        compile_prefix = re.compile(file_name_regexp_pattern)
        filtered_files = list(filter(compile_prefix.search, file_list))

        return filtered_files

    def _get_search_conditions(self, trackor_filter: dict, file_name: str) -> str:
        search_conditions = trackor_filter['searchConditions']
        for conditions_params in trackor_filter['searchConditionsParams']:
            param_name = conditions_params['paramName'] if 'paramName' in conditions_params else None
            param_regexp_pattern = conditions_params['paramValueRegexp'] if 'paramValueRegexp' in conditions_params else None

            value_from_file_name = self._get_value_from_file_name(file_name, param_regexp_pattern)
            if value_from_file_name is None:
                self._module_log.add(LogLevel.WARNING,
                    f'Failed to get value for regexp pattern "{param_regexp_pattern}" ' \
                    f'from file name "{file_name}" for trackor filter')

            search_conditions = search_conditions.replace(f':{param_name}', value_from_file_name)

        return search_conditions

    def _get_value_from_file_name(self, file_name: str, regexp_pattern: str) -> str:
        compile_prefix = re.compile(regexp_pattern)
        value_from_file_name = compile_prefix.search(file_name)
        if value_from_file_name is not None:
            value_from_file_name = value_from_file_name.group(1)

        return value_from_file_name

    def _process_file_data(self, sftp: Connection, field_name: str, file_name: str, trackor_data: list, trackor_type: str) -> None:
        try:
            self._sftp_service.download_file(sftp, file_name)
            is_file_exists = os.path.exists(file_name)
            if is_file_exists:
                self._module_log.add(LogLevel.DEBUG, f'File "{file_name}" has been downloaded')

                for trackor in trackor_data:
                    self._trackor_service.upload_file(trackor_type, trackor[TrackorService.TRACKOR_ID], field_name, file_name)

                self._sftp_service.move_to_archive(sftp, file_name)
                self._module_log.add(LogLevel.INFO, f'File "{file_name}" has been uploaded and moved to the archive')
            else:
                self._module_log.add(LogLevel.WARNING, f'File "{file_name}" has not been downloaded')
        finally:
            try:
                os.remove(file_name)
                self._module_log.add(LogLevel.DEBUG, f'File "{file_name}" has been deleted')
            except FileNotFoundError:
                pass


class TrackorService:
    TRACKOR_ID = 'TRACKOR_ID'
    TRACKOR_KEY = 'TRACKOR_KEY'

    def __init__(self, ov_url: str, settings_data: dict) -> None:
        self._ov_url = ov_url
        self._ov_access_key = settings_data['ovAccessKey']
        self._ov_secret_key = settings_data['ovSecretKey']

    def get_trackors(self, trackor_type: str, search_value: str) -> list:
        ov_trackor_type = Trackor(trackorType=trackor_type, URL=self._ov_url,
            userName=self._ov_access_key, password=self._ov_secret_key, isTokenAuth=True)

        ov_trackor_type.read(
            search=search_value,
            fields={TrackorService.TRACKOR_KEY}
        )

        if len(ov_trackor_type.errors) != 0:
            raise ModuleError(f'Failed to get trackors equal to "{search_value}"', ov_trackor_type.errors)

        return ov_trackor_type.jsonData

    def upload_file(self, trackor_type: str, trackor_id: int, field_name: str, file_name: str) -> list:
        ov_trackor_type = Trackor(trackorType=trackor_type, URL=self._ov_url,
            userName=self._ov_access_key, password=self._ov_secret_key, isTokenAuth=True)

        ov_trackor_type.UploadFile(
            trackorId=trackor_id,
            fieldName=field_name,
            fileName=file_name
        )

        if len(ov_trackor_type.errors) != 0:
            raise ModuleError(f'Failed to upload the file "{file_name}" for Trackor ID "{trackor_id}"',
                ov_trackor_type.errors)

        return ov_trackor_type.jsonData


class SFTPService:

    def __init__(self, settings_data: dict) -> None:
        self._url = settings_data['sftpUrl']
        self._username = settings_data['sftpUserName']
        self._password = settings_data['sftpPassword']
        self._directory = settings_data['sftpDirectory']
        self._archive = settings_data['sftpDirectoryArchive']
        self._cnopts = SFTPHelper()

    def connect(self) -> Connection:
        try:
            return Connection(host=self._url, username=self._username, password=self._password, cnopts=self._cnopts)
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
            raise ModuleError(f'Failed to download the file "{file_name}"', exception) from exception

    def move_to_archive(self, sftp: Connection, file_name: str) -> None:
        try:
            sftp.rename(f'{self._directory}{file_name}', f'{self._archive}{file_name}')
        except Exception as exception:
            raise ModuleError(f'Failed to move the file "{file_name}" from {self._directory}{file_name} ' \
                f'to {self._archive}{file_name}', exception) from exception


class SFTPHelper:

    def __init__(self, log=False, compression=False, ciphers=None, hostkeys=None):
        self.log = log
        self.compression = compression
        self.ciphers = ciphers
        self.hostkeys = hostkeys


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
