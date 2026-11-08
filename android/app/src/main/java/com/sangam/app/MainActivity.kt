package com.sangam.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.razorpay.PaymentData
import com.razorpay.PaymentResultWithDataListener
import com.sangam.app.network.TokenManager
import com.sangam.app.ui.navigation.Routes
import com.sangam.app.ui.navigation.SangamNavHost
import com.sangam.app.ui.screens.RazorpayState
import com.sangam.app.ui.theme.SangamTheme

class MainActivity : ComponentActivity(), PaymentResultWithDataListener {
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

    override fun onPaymentSuccess(razorpayPaymentId: String?, data: PaymentData?) {
        val signature = data?.signature
        if (razorpayPaymentId != null && data?.orderId != null && !signature.isNullOrBlank()) {
            RazorpayState.pendingListener?.invoke(razorpayPaymentId, data.orderId, signature)
        } else {
            RazorpayState.pendingErrorListener?.invoke("Payment succeeded but the signature was missing")
        }
        RazorpayState.pendingListener = null
        RazorpayState.pendingErrorListener = null
    }

    override fun onPaymentError(code: Int, response: String?, data: PaymentData?) {
        RazorpayState.pendingErrorListener?.invoke(response ?: "Payment failed (code $code)")
        RazorpayState.pendingListener = null
        RazorpayState.pendingErrorListener = null
    }
}
