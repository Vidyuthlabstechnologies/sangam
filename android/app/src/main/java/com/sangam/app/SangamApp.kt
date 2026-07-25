package com.sangam.app

import android.app.Application
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.TokenManager

class SangamApp : Application() {
    override fun onCreate() {
        super.onCreate()
        TokenManager.init(this)
        if (TokenManager.isLoggedIn()) {
            RealtimeClient.start()
        }
        try {
            Class.forName("com.google.firebase.FirebaseApp")
            com.google.firebase.FirebaseApp.initializeApp(this)
        } catch (_: Exception) { }
    }

    override fun onTerminate() {
        RealtimeClient.stop()
        super.onTerminate()
    }
}
