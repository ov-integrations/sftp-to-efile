# sftp-to-efile

Module retrieves files from SFTP, filters them by the parameters set in the settings file and uploads them to OneVizion.
In OneVizion, the Module gets Trackors ID for Project Trackor Type with status equal to 'Active' and Fuze ID equal to the one in the file name.

Example of settings.json

```json
{
    "sftpUrl": "***.onevizion.com",
    "sftpUserName": "******",
    "sftpPassword": "************",
    "sftpDirectory": "/home/zzz/Inbound/",
    "sftpDirectoryArchive": "/home/zzz/Inbound/Archive/",
    "sftpFileNameRegexpPattern": "\\w+_\\w+_\\w+_\\d{8}_\\d+.zip",
    "sftpFuzeIdRegexpPattern": "([a-zA-Z]+\\d+|\\d+)\\.",

    "ovUrl": "https://***.onevizion.com/",
    "ovAccessKey": "******",
    "ovSecretKey": "************"
}
```
