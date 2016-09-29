# 4d-plugin-activate
Move current application to front.

###Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
|🆗|🆗|🆗|🆗|

###Version

[v15](https://cloud.githubusercontent.com/assets/1725068/18940648/2192ddba-8645-11e6-864d-6d5692d55717.png){: height="32px" width="32px"}
[v16](https://cloud.githubusercontent.com/assets/1725068/18940649/21945000-8645-11e6-86ed-4a0f800e5a73.png){: height="32px" width="32px"}

###Introduction

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

This plugin is to illustrate how the new entry point can be used to manipulate the MDI window on v16.

###Note

In previous versions, it was possible to bring the current application to the front, using some code like this:

```
LAUNCH EXTERNAL PROCESS("cmd.exe /C \""+Application file\"")
```

Since v16, this will simply launch a new instance of 4D, as is expective of a modern Windows application. This plugin may serve as a workaround for such demands.
