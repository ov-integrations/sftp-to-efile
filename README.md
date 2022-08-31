# sftp-to-efile

Module retrieves files from SFTP, filters them by file name using parameters set in the settings file and uploads them to OneVizion.


* sftpFileNameRegexpPattern* - a regexp pattern, which is used to select files from the SFTP
* ovTrackorType* - target Trackor Type name
* ovEfileFieldName* - target EFile field name
* ovFieldMappings* - object. Parameters in it determine which Trackors need to be updated, using the received files. Object contains:
  * searchConditions* - search string. More details can be found in the API documentation in the trackors section in Search Trackors. Either a constant or parameter names are used as values
  * searchConditionsParams - objects list. Object contains:
    * paramName - parameter name. It must be written instead of values in searchConditions
    * regexpPattern - a regexp pattern
    * removePart - it is needed to remove some of what will be found with regexpPattern, to do this use replace, which removes what is specified in this parameter


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
            "sftpFileNameRegexpPattern": "^\\w+_\\w+_\\w+_\\d{8}_\\d{6}_([a-zA-Z]+\\d+|\\d+)\\.zip",
            "ovTrackorType": "Project",
            "ovEfileFieldName": "P_MMUAT_FILE_SA",
            "ovFieldMappings": {
                "searchConditions": "equal(P_FUZE_PROJECT_ID_FZ,:value1) and equal(P_PROJECT_STATUS,Active)",
                "searchConditionsParams": [
                    {
                        "paramName": "value1",
                        "regexpPattern": "([a-zA-Z]+\\d+|\\d+)\\.zip$",
                        "removePart": ".zip"
                    }
                ]
            }
        },
        {
            "sftpFileNameRegexpPattern": "^[a-zA-Z0-9]+\\-[A-Z]+\\-\\d+_LTE_\\w+_[a-zA-Z0-9]+_[0-9-]+_\\d{6}\\.zip",
            "ovTrackorType": "Project",
            "ovEfileFieldName": "P_LTE_ENV",
            "ovFieldMappings": {
                "searchConditions": "equal(TRACKOR_KEY,:value1)",
                "searchConditionsParams": [
                    {
                        "paramName": "value1",
                        "regexpPattern": "^[a-zA-Z0-9]+\\-[A-Z]+\\-\\d+"
                    }
                ]
            }
        }
    ]
}
```
