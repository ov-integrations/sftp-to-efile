from re import compile, Pattern
import os
from pysftp import Connection
from onevizion import LogLevel, IntegrationLog, Trackor


class Module:

    def __init__(self, ov_module_log: IntegrationLog, ov_url: str, settings_data: dict) -> None:
        self._module_log = ov_module_log
        self._sftp_service = SFTPService(settings_data)
        self._trackor_service = TrackorService(ov_url, settings_data)
        self._file_name_regexp_pattern = compile(settings_data['sftpFileNameRegexpPattern'])
        self._fuze_id_regexp_pattern = compile(settings_data['sftpFuzeIdRegexpPattern'])

    def start(self):
        self._module_log.add(LogLevel.INFO, 'Starting Module')

        with self._sftp_service.connect() as sftp:
            file_list = self._sftp_service.get_file_list(sftp)
            filtered_file_list = list(filter(self._file_name_regexp_pattern.search, file_list))
            self._module_log.add(LogLevel.INFO, f'{len(filtered_file_list)} files found')

            for file_name in filtered_file_list:
                fuze_id = self._get_fuze_id(file_name, self._fuze_id_regexp_pattern)
                trackor_data = self._trackor_service.get_trackors(fuze_id)
                filtered_trackors = self._filter_trackors(trackor_data, fuze_id)
                self._module_log.add(LogLevel.INFO, f'{len(filtered_trackors)} Trackors found for the file "{file_name}"')
                if len(filtered_trackors) > 0:
                    self._process_file_data(sftp, file_name, filtered_trackors)

        self._module_log.add(LogLevel.INFO, 'Module has been completed')

    def _get_fuze_id(self, file_name: str, fuze_id_regexp_pattern: Pattern) -> str:
        fuze_id = fuze_id_regexp_pattern.search(file_name)
        if fuze_id is not None:
            fuze_id = fuze_id.group()[:-1]

        return fuze_id

    def _filter_trackors(self, trackor_data: list, fuze_id: str) -> list:
        filtered_trackors = []
        for trackor in trackor_data:
            if trackor[TrackorService.FUZE_ID_FILED] == fuze_id:
                filtered_trackors.append(trackor[TrackorService.TRACKOR_ID])

        return filtered_trackors

    def _process_file_data(self, sftp: Connection, file_name: str, filtered_trackors: list) -> None:
        try:
            self._sftp_service.download_file(sftp, file_name)
            is_file_exists = os.path.exists(file_name)
            if is_file_exists:
                self._module_log.add(LogLevel.DEBUG, f'File "{file_name}" has been downloaded')

                for trackor in filtered_trackors:
                    self._trackor_service.upload_file(trackor, file_name)

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
    PROJECT_STATUS_FIELD = 'P_PROJECT_STATUS'
    FUZE_ID_FILED = 'P_FUZE_PROJECT_ID_FZ'
    EFILE_FIELD = 'P_MMUAT_FILE_SA'
    PROJECT_STATUS_ACTIVE_VALUE = 'Active'

    def __init__(self, ov_url: str, settings_data: dict) -> None:
        self._ov_trackor_type = Trackor(trackorType='Project', URL=ov_url, userName=settings_data['ovAccessKey'],
                                        password=settings_data['ovSecretKey'], isTokenAuth=True)

    def get_trackors(self, fuze_id: str) -> list:
        self._ov_trackor_type.read(
            filters={TrackorService.PROJECT_STATUS_FIELD: TrackorService.PROJECT_STATUS_ACTIVE_VALUE,
                     TrackorService.FUZE_ID_FILED: fuze_id},
            fields={TrackorService.FUZE_ID_FILED}
        )

        if len(self._ov_trackor_type.errors) == 0:
            return self._ov_trackor_type.jsonData

        raise ModuleError(f'Failed to get trackors for "{TrackorService.FUZE_ID_FILED}" field ' \
            f'equal to "{fuze_id}"', self._ov_trackor_type.errors)

    def upload_file(self, trackor_id: int, file_name: str) -> list:
        self._ov_trackor_type.UploadFile(
            trackorId=trackor_id,
            fieldName=TrackorService.EFILE_FIELD,
            fileName=file_name
        )

        if len(self._ov_trackor_type.errors) == 0:
            return self._ov_trackor_type.jsonData

        raise ModuleError(f'Failed to upload the file "{file_name}" for Trackor ID "{trackor_id}"',
                          self._ov_trackor_type.errors)


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
