package com.sangam.app

import android.app.Application
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.TokenManager

class SangamApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Firebase first: TokenManager.isLoggedIn() asks Firebase for the session.
        try {
            com.google.firebase.FirebaseApp.initializeApp(this)
        } catch (_: Exception) { }
        TokenManager.init(this)
        try {
            com.sangam.app.billing.Billing.configure(this, TokenManager.getActorId())
        } catch (_: Exception) { }
        if (TokenManager.isLoggedIn()) {
            RealtimeClient.start()
        }
    }

    override fun onTerminate() {
        RealtimeClient.stop()
        super.onTerminate()
    }
}
