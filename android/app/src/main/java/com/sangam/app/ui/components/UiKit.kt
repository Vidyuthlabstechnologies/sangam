package com.sangam.app.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException

/**
 * Turns an exception into a sentence a shop owner can act on. Raw messages such as
 * "Failed to connect to /10.0.2.2:8000" or "HTTP 500" mean nothing to them.
 */
fun friendlyError(e: Throwable?, action: String = "load this"): String = when (e) {
    is SocketTimeoutException -> "The connection is slow. Could not $action. Try again."
    is IOException -> "No connection to Sangamitra. Check your internet and try again."
    is HttpException -> when (e.code()) {
        401, 403 -> "Your session has expired. Sign out and sign in again."
        404 -> "Could not $action. It may have been removed."
        429 -> "Too many requests. Wait a minute and try again."
        in 500..599 -> "Sangamitra is having trouble right now. Could not $action. Try again in a few minutes."
        else -> "Could not $action (error ${e.code()}). Try again."
    }
    else -> "Could not $action. Try again."
}

/** Full-width error with a retry button, announced by screen readers when it appears. */
@Composable
fun ErrorState(message: String, onRetry: (() -> Unit)?, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 24.dp)
            .semantics { liveRegion = LiveRegionMode.Polite },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(Icons.Default.CloudOff, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            message,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center,
        )
        if (onRetry != null) {
            OutlinedButton(onClick = onRetry) { Text("Try again") }
        }
    }
}

/** The one back button every pushed screen uses, so it looks and reads the same everywhere. */
@Composable
fun BackButton(onBack: () -> Unit) {
    IconButton(onClick = onBack) {
        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
    }
}
