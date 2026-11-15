package com.sangam.app

import android.app.Activity
import android.app.Application
import android.os.Bundle
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.TokenManager

class SangamApp : Application() {
    override fun onCreate() {
        super.onCreate()
        com.sangam.app.ui.components.AppText.resources = resources
        // Firebase first: TokenManager.isLoggedIn() asks Firebase for the session.
        try {
            com.google.firebase.FirebaseApp.initializeApp(this)
        } catch (_: Exception) { }
        TokenManager.init(this)
        try {
            com.sangam.app.billing.Billing.configure(this, TokenManager.getActorId())
        } catch (_: Exception) { }
        registerActivityLifecycleCallbacks(ForegroundRealtime)
    }

    override fun onTerminate() {
        RealtimeClient.stop()
        super.onTerminate()
    }

    /**
     * Keep the live-updates socket open only while the app is on screen.
     *
     * Android keeps a backgrounded process alive for a long time. A socket held
     * from every such phone would occupy a server slot per install, keep the
     * backend billed as busy, and drain the phone's battery. Push notifications
     * cover the background.
     */
    private object ForegroundRealtime : ActivityLifecycleCallbacks {
        private var started = 0

        override fun onActivityStarted(activity: Activity) {
            started += 1
            if (started == 1 && TokenManager.isLoggedIn()) RealtimeClient.start()
        }

        override fun onActivityStopped(activity: Activity) {
            started = (started - 1).coerceAtLeast(0)
            if (started == 0) RealtimeClient.stop()
        }

        override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) {}
        override fun onActivityResumed(activity: Activity) {}
        override fun onActivityPaused(activity: Activity) {}
        override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) {}
        override fun onActivityDestroyed(activity: Activity) {}
    }
}
