/* --------------------------------------------------------------------------------
 #
 #	4DPlugin.cpp
 #	source generated by 4D Plugin Wizard
 #	Project : Activate
 #	author : miyako
 #	2016/09/29
 #
 # --------------------------------------------------------------------------------*/


#include "4DPluginAPI.h"
#include "4DPlugin.h"

#if VERSIONWIN

HWND gmdi = NULL;

void activateWindow(HWND window)
{
	ShowWindowAsync(window, SW_RESTORE);
	//ShowWindow(window, SW_RESTORE);
	SetWindowPos(window, HWND_TOP, 0, 0, 0, 0,  SWP_NOMOVE | SWP_NOSIZE);
	//SetActiveWindow(window);
	SetForegroundWindow(window);
	AllowSetForegroundWindow(ASFW_ANY);
}

HWND getMainWindow()
{
	HWND mdi = NULL;
	//get decimal (e.g. 15, 16...) version number
	PA_ulong32 version = (PA_Get4DVersion() & 0xFFFF);
	version = (version >> 8);
	version = (version & 0x000F) + ((version >> 4)* 10);
	
	if(version > 15)
	{
		mdi = GetMainHWND();
	}
	
	if(!mdi)
	{
		//the window class is the folder name of the application
		wchar_t path[_MAX_PATH] = {0};
		wcscpy(path, (const wchar_t *)PA_GetApplicationFullPath().fString);
		//remove file name (4D.exe)
		PathRemoveFileSpec(path);
		//check instance as well, to be sure
		HINSTANCE h = (HINSTANCE)PA_Get4DHInstance();
		do{
			mdi = FindWindowEx(NULL, mdi, (LPCTSTR)path, NULL);
			if(mdi){
				if(h == (HINSTANCE)GetWindowLongPtr(mdi, GWLP_HINSTANCE)){
					break;
				}
			}
		}while(mdi);
	}
	
	return mdi;
}
#endif

void PluginMain(PA_long32 selector, PA_PluginParameters params)
{
	try
	{
		PA_long32 pProcNum = selector;
		sLONG_PTR *pResult = (sLONG_PTR *)params->fResult;
		PackagePtr pParams = (PackagePtr)params->fParameters;

		CommandDispatcher(pProcNum, pResult, pParams); 
	}
	catch(...)
	{

	}
}

void CommandDispatcher (PA_long32 pProcNum, sLONG_PTR *pResult, PackagePtr pParams)
{
	switch(pProcNum)
	{
		case kInitPlugin :
		case kServerInitPlugin :
#if VERSIONWIN
			gmdi = getMainWindow();
#endif
			break;
// --- Activate

		case 1 :
			ACTIVATE_4D(pResult, pParams);
			break;

	}
}

// ----------------------------------- Activate -----------------------------------

#if VERSIONWIN
HWND getHWND(){

}
#endif

void ACTIVATE_4D(sLONG_PTR *pResult, PackagePtr pParams)
{
#if VERSIONMAC
	[[NSRunningApplication currentApplication]activateWithOptions:NSApplicationActivateIgnoringOtherApps];
#endif
	
#if VERSIONWIN
	activateWindow(gmdi);
#endif
}

