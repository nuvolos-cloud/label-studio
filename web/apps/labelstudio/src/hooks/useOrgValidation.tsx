import { useEffect } from "react";
import { ToastType, useToast } from "@humansignal/ui";

/**
 * Creates a shared AbortController, which can be used to abort requests.
 * Automatically cancels the current controller when the component unmounts.
 */
export const useOrgValidation = (): void => {
  const toast = useToast();

  useEffect(() => {
    console.log('[useOrgValidation] window.APP_SETTINGS:', window.APP_SETTINGS);
    console.log('[useOrgValidation] window.APP_SETTINGS?.flags:', window.APP_SETTINGS?.flags);
    console.log('[useOrgValidation] storage_persistence flag:', window.APP_SETTINGS?.flags?.storage_persistence);
    
    if (window.APP_SETTINGS?.flags?.storage_persistence) {
      console.log('[useOrgValidation] Storage persistence is enabled, skipping warning');
      return;
    }
    
    console.log('[useOrgValidation] Storage persistence is NOT enabled, showing warning');
    toast.show({
      message: (
        <>
          Data will be persisted on the node running this container, but all data will be lost if this node goes away.
        </>
      ),
      type: ToastType.alertError,
      duration: -1,
    });
  }, []);
};
