package com.sangam.app.ui.components

import com.sangam.app.R

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonColors
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException

/**
 * Turns an exception into a sentence a shop owner can act on. Raw messages such as
 * "Failed to connect to /10.0.2.2:8000" or "HTTP 500" mean nothing to them.
 */
fun friendlyError(e: Throwable?, action: String = str(R.string.load_this)): String = when (e) {
    is SocketTimeoutException -> str(R.string.the_connection_is_slow_could_not, action)
    is IOException -> str(R.string.no_connection_to_sangamitra_check_your)
    is HttpException -> when (e.code()) {
        401, 403 -> str(R.string.your_session_has_expired_sign_out)
        404 -> str(R.string.could_not_it_may_have_been, action)
        429 -> str(R.string.too_many_requests_wait_a_minute)
        in 500..599 -> str(R.string.sangamitra_is_having_trouble_right_now, action)
        else -> str(R.string.could_not_error_try_again, action, e.code())
    }
    else -> str(R.string.could_not_try_again, action)
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
            SecondaryButton(onClick = onRetry) { Text(str(R.string.try_again)) }
        }
    }
}

/** The one back button every pushed screen uses, so it looks and reads the same everywhere. */
@Composable
fun BackButton(onBack: () -> Unit) {
    IconButton(onClick = onBack) {
        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = str(R.string.back))
    }
}

/*
 * One button family for the whole app. Material's defaults are fully round pills of
 * 40dp, which looked like chips next to our 12dp-corner cards and text fields, and fell
 * under the 48dp touch target. Every screen uses these instead of Button/OutlinedButton.
 */
val ButtonShape = RoundedCornerShape(12.dp)
private val ButtonPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp)

/** The one main action on a screen or card: solid black. */
@Composable
fun PrimaryButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: ButtonColors = ButtonDefaults.buttonColors(
        disabledContainerColor = MaterialTheme.colorScheme.surfaceContainerHighest,
        disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ),
    contentPadding: PaddingValues = ButtonPadding,
    content: @Composable RowScope.() -> Unit,
) {
    Button(
        onClick = onClick,
        modifier = modifier.heightIn(min = 48.dp),
        enabled = enabled,
        shape = ButtonShape,
        colors = colors,
        contentPadding = contentPadding,
        content = content,
    )
}

/** Other actions: white with a visible grey edge. */
@Composable
fun SecondaryButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: ButtonColors = ButtonDefaults.outlinedButtonColors(
        contentColor = MaterialTheme.colorScheme.onSurface,
    ),
    border: BorderStroke? = BorderStroke(
        1.dp,
        if (enabled) MaterialTheme.colorScheme.outline else MaterialTheme.colorScheme.outlineVariant,
    ),
    contentPadding: PaddingValues = ButtonPadding,
    content: @Composable RowScope.() -> Unit,
) {
    androidx.compose.material3.OutlinedButton(
        onClick = onClick,
        modifier = modifier.heightIn(min = 48.dp),
        enabled = enabled,
        shape = ButtonShape,
        colors = colors,
        border = border,
        contentPadding = contentPadding,
        content = content,
    )
}

/** Low-emphasis actions inside cards and dialogs. Same height so rows line up. */
@Composable
fun TertiaryButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: ButtonColors = ButtonDefaults.textButtonColors(),
    content: @Composable RowScope.() -> Unit,
) {
    TextButton(
        onClick = onClick,
        modifier = modifier.heightIn(min = 48.dp),
        enabled = enabled,
        shape = ButtonShape,
        colors = colors,
        content = content,
    )
}

/**
 * A read-only status tag. Outlined chips looked like buttons that did nothing, so a
 * status is a filled label with no border.
 */
@Composable
fun StatusLabel(
    text: String,
    modifier: Modifier = Modifier,
    container: Color = MaterialTheme.colorScheme.secondaryContainer,
    content: Color = MaterialTheme.colorScheme.onSecondaryContainer,
) {
    Surface(modifier = modifier, shape = RoundedCornerShape(8.dp), color = container, contentColor = content) {
        Text(
            text,
            style = MaterialTheme.typography.labelLarge,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** Backend enums ("ai_agent", "PENDING") as words: "Ai agent" becomes "AI agent". */
fun humanize(raw: String): String = raw.lowercase().replace('_', ' ')
    .replaceFirstChar { it.uppercase() }
    .replace(Regex("\\bai\\b", RegexOption.IGNORE_CASE), "AI")
