# sftp-to-efile

Module retrieves files from SFTP, filters them by file name using parameters set in the settings file and uploads them to OneVizion.


* sftpFileNameRegexp* - a regexp pattern, which is used to select files from the SFTP
* sftpArchiveFileRetentionDays - if filled, the files will be deleted from the archive after the specified number of days
* ovTrackorType* - target Trackor Type name
* ovEfileFieldName* - target EFile field name
* ovTrackorFilter* - object. Parameters in it determine which Trackors need to be updated, using the received files. Object contains:
  * searchConditions* - search string. More details can be found in the API documentation in the trackors section in Search Trackors. Either a constant or parameter names are used as values
  * searchConditionsParams - objects list. Object contains:
    * paramName - parameter name. It must be written instead of values in searchConditions
    * paramValueRegexp - a regexp pattern. Applies to the file name and gets the value from it


Example of settings.json

```json
{
    "sftpUrl": "***.onevizion.com",
    "sftpUserName": "******",
    "sftpPassword": "************",
    "sftpDirectory": "/home/zzz/Inbound/",
    "sftpDirectoryArchive": "/home/zzz/Inbound/Archive/",

    "ovUrl": "https://***.onevizion.com/",
    "ovAccessKey": "******",
    "ovSecretKey": "************",

    "sftpFileToOvMappings": [
        {
            "sftpFileNameRegexp": "^\\w+_\\w+_\\w+_\\d{8}_\\d{6}_([a-zA-Z0-9]+)\\.zip",
            "ovTrackorType": "Project",
            "ovEfileFieldName": "P_MMUAT_FILE_SA",
            "ovTrackorFilter": {
                "searchConditions": "equal(P_FUZE_PROJECT_ID_FZ,\\\":value1\\\") and equal(P_PROJECT_STATUS,Active)",
                "searchConditionsParams": [
                    {
                        "paramName": "value1",
                        "paramValueRegexp": "([a-zA-Z0-9]+)\\.zip$"
                    }
                ]
            }
        },
        {
            "sftpFileNameRegexp": "^(.+?)_LTE_(.+)_[0-9-]+_\\d{6}\\.zip",
            "ovTrackorType": "Project",
            "ovEfileFieldName": "P_LTE_ENV",
            "ovTrackorFilter": {
                "searchConditions": "equal(TRACKOR_KEY,:value1)",
                "searchConditionsParams": [
                    {
                        "paramName": "value1",
                        "paramValueRegexp": "^(.+?)_"
                    }
                ]
            }
        }
    ]
}
```
