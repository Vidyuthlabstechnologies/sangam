package com.sangam.app.notification

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.sangam.app.MainActivity
import com.sangam.app.R
import com.sangam.app.network.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class SangamFirebaseService : FirebaseMessagingService() {

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        CoroutineScope(Dispatchers.IO).launch {
            try {
                ApiClient.api.registerFcmToken(com.sangam.app.network.FCMTokenRequest(token))
            } catch (_: Exception) { }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val title = message.notification?.title ?: message.data["title"] ?: "Sangam"
        val body = message.notification?.body ?: message.data["body"] ?: ""
        val workflowId = message.data["workflow_id"]
        val event = message.data["event"]
        showNotification(title, body, workflowId, event)
    }

    private fun showNotification(
        title: String,
        body: String,
        workflowId: String?,
        event: String?,
    ) {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            workflowId?.let { putExtra("workflow_id", it) }
            event?.let { putExtra("event", it) }
        }

        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val defaults = when (event) {
            "sla_breach", "exception_raised", "workflow_failed" ->
                NotificationCompat.DEFAULT_SOUND or NotificationCompat.DEFAULT_VIBRATE
            else -> NotificationCompat.DEFAULT_ALL
        }

        val notification = NotificationCompat.Builder(this, CHANNEL_GENERAL)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setDefaults(defaults)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        try {
            NotificationManagerCompat.from(this).notify(
                System.currentTimeMillis().toInt(),
                notification,
            )
        } catch (_: SecurityException) { }
    }

    private fun createNotificationChannels() {
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_GENERAL,
                    "General Notifications",
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = "Workflow updates, approvals, and alerts"
                },
            )
            manager.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_SLA,
                    "SLA Alerts",
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = "SLA warnings and breaches"
                },
            )
            manager.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_PAYMENT,
                    "Payment Updates",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "Payment confirmations and refunds"
                },
            )
        }
    }

    companion object {
        const val CHANNEL_GENERAL = "sangam_general"
        const val CHANNEL_SLA = "sangam_sla"
        const val CHANNEL_PAYMENT = "sangam_payment"
    }
}
