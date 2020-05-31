# 4d-plugin-activate
Move current application to front.

### Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
||<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|

### Version

<img width="32" height="32" src="https://user-images.githubusercontent.com/1725068/73986501-15964580-4981-11ea-9ac1-73c5cee50aae.png"> <img src="https://user-images.githubusercontent.com/1725068/73987971-db2ea780-4984-11ea-8ada-e25fb9c3cf4e.png" width="32" height="32" />

### Feature

On Mac, the app is activated (``NSRunningApplication activateWithOptions:``)

On Windows MDI mode, the MDI window is restored and activated. ``$1`` is ignored. After that, you would want to ``BRING TO FRONT`` the ``Current process``.

On Windows SDI mode, pass a window reference in ``$1``.

### Discussion (reference)

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

```c
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

In previous versions, it was possible to bring the current application to the front, using some code like this:

```
LAUNCH EXTERNAL PROCESS("cmd.exe /C \""+Application file\"")
```

Since v16, this will simply launch a new instance of 4D, as is expective of a modern Windows application. This plugin may serve as a workaround for such demands.

~~Following [SetForegroundWindow](https://msdn.microsoft.com/en-us/library/windows/desktop/ms633539(v=vs.85).aspx) recommendations, the plugin does **not** attempt to steal the foreground status from the current foreground application.~~

See also [console-activate-4d](https://github.com/miyako/console-activate-4d)
