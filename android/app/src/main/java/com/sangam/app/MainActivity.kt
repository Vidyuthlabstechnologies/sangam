package com.sangam.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.sangam.app.network.TokenManager
import com.sangam.app.ui.navigation.Routes
import com.sangam.app.ui.navigation.SangamNavHost
import com.sangam.app.ui.theme.SangamTheme

class MainActivity : ComponentActivity() {
    // Applies the in-app language on Android 12 and older; 13+ handles it natively.
    override fun attachBaseContext(newBase: android.content.Context) {
        super.attachBaseContext(com.sangam.app.ui.components.AppLanguage.wrap(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            SangamTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val navController = rememberNavController()
                    val startDest = if (TokenManager.isLoggedIn()) Routes.DASHBOARD else Routes.LOGIN
                    SangamNavHost(navController = navController, startDestination = startDest)
                }
            }
        }
    }
}
