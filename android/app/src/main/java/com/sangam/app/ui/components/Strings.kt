package com.sangam.app.ui.components

import android.content.res.Resources
import androidx.annotation.StringRes

/**
 * Localised text from anywhere, including coroutines and plain functions that have no
 * Composable context (error mappers, callbacks). The activity's resources are set by
 * SangamTheme, so they follow the language the user picked; the activity is recreated
 * when that changes.
 */
object AppText {
    @Volatile
    var resources: Resources? = null
}

fun str(@StringRes id: Int, vararg args: Any?): String {
    val res = AppText.resources ?: return ""
    return if (args.isEmpty()) res.getString(id) else res.getString(id, *args)
}
