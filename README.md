# 4d-plugin-activate
Move current application to front.

##Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
|🆗|🆗|🆗|🆗|

#About

4D v16 is the very first non-Altura (Mac2Win) release for the Windows platform. In particular, some core modules have been re-written (or replaced, for memory management) to be Altura free:

* Window manager
* Menu manager
* Resources manager
* Memory Manager

As a consequence, the conventional method to manipulate the MDI window does not work anymore:

```c
#include "Shlwapi.h"
#pragma comment(lib, "Shlwapi.lib")

HWND mdi = NULL;
//the window class is the folder name of the application
wchar_t path[_MAX_PATH] = {0};
wcscpy(path, (const wchar_t *)PA_GetApplicationFullPath().fString);
//remove file name (4D.exe)
PathRemoveFileSpec(path);
HINSTANCE h = (HINSTANCE)PA_Get4DHInstance();
do{
  mdi = FindWindowEx(NULL, mdi, (LPCTSTR)path, NULL);
  if(mdi){
    if(h == (HINSTANCE)GetWindowLongPtr(mdi, GWLP_HINSTANCE)){
      break;
    }
  }
}while(mdi);
```

A new entry point has been added (``719``) in v16, which will return the ``HWND`` of the MDI window.

```
HWND GetMainHWND()
{
	EngineBlock eb;
	eb.fParam1 = 0;
	eb.fError  = 0;
	Call4D( 719, &eb );
	sErrorCode = (PA_ErrorCode) eb.fError;
	return sErrorCode == 0 ? (HWND)eb.fParam1 : NULL;
}
```
