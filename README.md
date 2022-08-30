# sftp-to-efile

Module retrieves files from SFTP, filters them by file name using parameters set in the settings file and uploads them to OneVizion.

You need to fill in the regexpPatterns parameter to specify what data the Module should receive.
  * sftpFileNameRegexpPattern - contains a regexp pattern, which is used to select files from the sftp
  * ovTrackorType - contains the Trackor Type to which the files will be transferred
  * ovEfileFieldName - contains the name of the field to which the files will be transferred
  * ovTrackorFilters - list of dictionaries with data that will be used to filter Trackors
    * searchTrigger - the filter itself. It must match the following construction "equal(FIELD_NAME,VALUE)" or "not equal(FIELD_NAME,VALUE)"

    The VALUE value can either be a constant and then you only have to specify the searchTrigger parameter and that value in it. Otherwise, if the value is not a constant, you must specify it as "{value}" and also add the valueTrigger parameter.
    * valueTrigger - dictionary containing regexp pattern for selecting data from filename
      * regexpPattern - contains a regexp pattern
      * removePart - is not a required parameter, it is needed to remove some of what will be found with regexpPattern. replace is used for this, it removes what is specified in this parameter.

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

    "regexpPatterns": [
        {
            "sftpFileNameRegexpPattern": "^\\w+_\\w+_\\w+_\\d{8}_\\d{6}_([a-zA-Z]+\\d+|\\d+)\\.zip",
            "ovTrackorType": "Project",
            "ovTrackorFilters": [
                {
                    "searchTrigger": "equal(P_FUZE_PROJECT_ID_FZ,{value})",
                    "valueTrigger": {
                        "regexpPattern": "([a-zA-Z]+\\d+|\\d+)\\.zip$",
                        "removePart": ".zip"
                    }
                },
                {
                    "searchTrigger": "equal(P_PROJECT_STATUS,Active)"
                }
            ],
            "ovEfileFieldName": "P_MMUAT_FILE_SA"
        },
        {
            "sftpFileNameRegexpPattern": "^[a-zA-Z0-9]+\\-[A-Z]+\\-\\d+_LTE_\\w+_[a-zA-Z0-9]+_[0-9-]+_\\d{6}\\.zip",
            "ovTrackorType": "Project",
            "ovTrackorFilters": [
                {
                    "searchTrigger": "equal(TRACKOR_KEY,{value})",
                    "valueTrigger": {
                        "regexpPattern": "^[a-zA-Z0-9]+\\-[A-Z]+\\-\\d+"
                    }
                }
            ],
            "ovEfileFieldName": "P_LTE_ENV"
        }
    ]
}
```
