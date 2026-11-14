package com.sangam.app.ui.components

import android.app.Activity
import android.app.LocaleManager
import android.content.Context
import android.content.res.Configuration
import android.os.Build
import android.os.LocaleList
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.sangam.app.R
import java.util.Locale

/** App languages, each named in its own script so anyone can find theirs. Empty tag = phone's language. */
val APP_LANGUAGES = listOf(
    "" to null,
    "en" to "English",
    "hi" to "हिन्दी",
    "bn" to "বাংলা",
    "te" to "తెలుగు",
    "mr" to "मराठी",
    "ta" to "தமிழ்",
    "gu" to "ગુજરાતી",
    "kn" to "ಕನ್ನಡ",
    "ml" to "മലയാളം",
    "or" to "ଓଡ଼ିଆ",
    "pa" to "ਪੰਜਾਬੀ",
)

/**
 * Per-app language. Android 13+ stores it itself (and shows it in system settings);
 * older versions keep it in prefs and MainActivity applies it in attachBaseContext.
 */
object AppLanguage {
    private const val PREFS = "app_language"
    private const val KEY = "tag"

    fun current(context: Context): String =
        if (Build.VERSION.SDK_INT >= 33) {
            context.getSystemService(LocaleManager::class.java).applicationLocales.toLanguageTags().substringBefore(',')
        } else {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, "").orEmpty()
        }

    fun set(activity: Activity, tag: String) {
        if (Build.VERSION.SDK_INT >= 33) {
            activity.getSystemService(LocaleManager::class.java).applicationLocales =
                if (tag.isEmpty()) LocaleList.getEmptyLocaleList() else LocaleList.forLanguageTags(tag)
        } else {
            activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, tag).apply()
            activity.recreate()
        }
    }

    /** For MainActivity.attachBaseContext on Android 12 and older. */
    fun wrap(base: Context): Context {
        if (Build.VERSION.SDK_INT >= 33) return base
        val tag = base.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, "").orEmpty()
        if (tag.isEmpty()) return base
        val locale = Locale.forLanguageTag(tag)
        Locale.setDefault(locale)
        val config = Configuration(base.resources.configuration)
        config.setLocale(locale)
        return base.createConfigurationContext(config)
    }
}

@Composable
fun LanguageDialog(onDismiss: () -> Unit) {
    val context = LocalContext.current
    val selected = AppLanguage.current(context)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(str(R.string.app_language)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                APP_LANGUAGES.forEach { (tag, label) ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp)
                            .clickable(role = Role.RadioButton) {
                                onDismiss()
                                if (tag != selected) AppLanguage.set(context as Activity, tag)
                            }
                            .padding(horizontal = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = tag == selected, onClick = null)
                        Text(
                            label ?: str(R.string.phone_language),
                            style = MaterialTheme.typography.bodyLarge,
                            modifier = Modifier.padding(start = 12.dp),
                        )
                    }
                }
            }
        },
        confirmButton = { TertiaryButton(onClick = onDismiss) { Text(str(R.string.cancel)) } },
    )
}
