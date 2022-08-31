import re
import os
from pysftp import Connection
from onevizion import LogLevel, IntegrationLog, Trackor


class Module:
    SEARCH_FIELD_PATTERN = 'equal\\([a-zA-Z0-9_]+,' # Example: equal(FIELD_NAME123,XXXX)

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
                regexp_pattern = sftp_file_to_ov_mapping['sftpFileNameRegexpPattern']
                filtered_file_list = self._filter_files(file_list, regexp_pattern)
                self._module_log.add(LogLevel.INFO, f'{len(filtered_file_list)} files found for the regexp pattern "{regexp_pattern}"')

                for file_name in filtered_file_list:
                    field_mappings = sftp_file_to_ov_mapping['ovFieldMappings']
                    search_conditions = self._get_search_conditions(field_mappings, file_name)
                    trackor_fields = self._get_trackor_fields(field_mappings['searchConditions'])
                    trackor_data = self._trackor_service.get_trackors(trackor_type, trackor_fields, search_conditions)
                    filtered_trackors = self._filter_trackors(trackor_fields, trackor_data, search_conditions)
                    self._module_log.add(LogLevel.INFO, f'{len(filtered_trackors)} Trackors found for the file "{file_name}"')
                    if len(trackor_data) > 0:
                        self._process_file_data(sftp, sftp_file_to_ov_mapping['ovEfileFieldName'], file_name,
                            filtered_trackors, trackor_type)

        self._module_log.add(LogLevel.INFO, 'Module has been completed')

    def _filter_files(self, file_list: list, file_name_regexp_pattern: str) -> list:
        compile_prefix = re.compile(file_name_regexp_pattern)
        filtered_files = list(filter(compile_prefix.search, file_list))

        return filtered_files

    def _get_search_conditions(self, field_mappings: dict, file_name: str) -> str:
        search_conditions = field_mappings['searchConditions']
        for conditions_params in field_mappings['searchConditionsParams']:
            value_from_file_name = None
            param_name = conditions_params['paramName'] if 'paramName' in conditions_params else None
            regexp_pattern = conditions_params['regexpPattern'] if 'regexpPattern' in conditions_params else None
            remove_part = conditions_params['removePart'] if 'removePart' in conditions_params else None

            value_from_file_name = self._get_value_from_file_name(file_name, regexp_pattern, remove_part)
            if value_from_file_name is None:
                self._module_log(LogLevel.WARNING,
                    f'Failed to get value for regexp pattern "{regexp_pattern}" ' \
                    f'from file name "{file_name}" for trackor filter')

            search_conditions = search_conditions.replace(f':{param_name}', value_from_file_name)

        return search_conditions

    def _get_value_from_file_name(self, file_name: str, regexp_pattern: str, remove_part: str) -> str:
        compile_prefix = re.compile(regexp_pattern)
        value_from_file_name = compile_prefix.search(file_name)
        if value_from_file_name is not None:
            value_from_file_name = value_from_file_name.group()

            if remove_part is not None:
                value_from_file_name = value_from_file_name.replace(remove_part, '')

        return value_from_file_name

    def _get_trackor_fields(self, search_conditions: str) -> str:
        trackor_fields = None
        for field in re.findall(Module.SEARCH_FIELD_PATTERN, search_conditions):
            field_name = field[len('equal('):-1]
            if trackor_fields is None:
                trackor_fields = field_name
            else:
                trackor_fields = f'{field_name},{trackor_fields}'

        return trackor_fields

    def _filter_trackors(self, trackor_fields: str, trackor_data: list, trackor_filter: str) -> list:
        filtered_trackors = []
        fields_list = re.split(',', trackor_fields)
        for trackor in trackor_data:
            is_values_match = True
            for field in fields_list:
                if re.search(trackor[field], trackor_filter) is None:
                    is_values_match = False
                    break

            if is_values_match:
                filtered_trackors.append(trackor[TrackorService.TRACKOR_ID])

        return filtered_trackors

    def _process_file_data(self, sftp: Connection, field_name: str, file_name: str, filtered_trackors: list, trackor_type: str) -> None:
        try:
            self._sftp_service.download_file(sftp, file_name)
            is_file_exists = os.path.exists(file_name)
            if is_file_exists:
                self._module_log.add(LogLevel.DEBUG, f'File "{file_name}" has been downloaded')

                for trackor in filtered_trackors:
                    self._trackor_service.upload_file(trackor_type, trackor, field_name, file_name)

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

    def __init__(self, ov_url: str, settings_data: dict) -> None:
        self._ov_url = ov_url
        self._ov_access_key = settings_data['ovAccessKey']
        self._ov_secret_key = settings_data['ovSecretKey']

    def get_trackors(self, trackor_type: str, field_name: str, search_value: str) -> list:
        ov_trackor_type = Trackor(trackorType=trackor_type, URL=self._ov_url,
            userName=self._ov_access_key, password=self._ov_secret_key, isTokenAuth=True)

        ov_trackor_type.read(
            search=search_value,
            fields={field_name}
        )

        if len(ov_trackor_type.errors) == 0:
            return ov_trackor_type.jsonData

        raise ModuleError(f'Failed to get trackors equal to "{search_value}"', ov_trackor_type.errors)

    def upload_file(self, trackor_type: str, trackor_id: int, field_name: str, file_name: str) -> list:
        ov_trackor_type = Trackor(trackorType=trackor_type, URL=self._ov_url,
            userName=self._ov_access_key, password=self._ov_secret_key, isTokenAuth=True)

        ov_trackor_type.UploadFile(
            trackorId=trackor_id,
            fieldName=field_name,
            fileName=file_name
        )

        if len(ov_trackor_type.errors) == 0:
            return ov_trackor_type.jsonData

        raise ModuleError(f'Failed to upload the file "{file_name}" for Trackor ID "{trackor_id}"',
            ov_trackor_type.errors)


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
