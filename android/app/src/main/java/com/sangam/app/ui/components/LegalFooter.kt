package com.sangam.app.ui.components

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.sangam.app.BuildConfig
import com.sangam.app.network.TokenManager

/** Public pages Play reviewers and users must be able to reach from the app. */
object LegalLinks {
    private fun fallback(path: String) = TokenManager.getServerUrl().trimEnd('/') + path

    // Fallbacks are the backend's own public pages (backend/app/api/legal.py). Release builds
    // set the *_URL values from CI variables so Play sees the Cloudflare-hosted copies.
    fun privacyPolicy(): String = BuildConfig.PRIVACY_POLICY_URL.ifBlank { fallback("/legal/privacy") }
    fun terms(): String = BuildConfig.TERMS_URL.ifBlank { fallback("/legal/terms") }
    fun accountDeletion(): String = BuildConfig.ACCOUNT_DELETION_URL.ifBlank { fallback("/legal/delete-account") }

    fun open(context: Context, url: String) {
        try {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: Exception) {
        }
    }
}

/** Privacy policy and terms links, plus the app version testers report bugs against. */
@Composable
fun LegalFooter(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    Column(modifier = modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Row(horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { LegalLinks.open(context, LegalLinks.privacyPolicy()) }) {
                Text("Privacy policy", style = MaterialTheme.typography.labelSmall)
            }
            TextButton(onClick = { LegalLinks.open(context, LegalLinks.terms()) }) {
                Text("Terms of use", style = MaterialTheme.typography.labelSmall)
            }
        }
        Text(
            "Version ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline,
        )
    }
}
