package com.sangam.app.network

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import android.util.Base64
import java.security.SecureRandom

object TokenManager {
    private const val PREFS_NAME = "sangam_prefs"
    private const val KEY_TOKEN = "jwt_token"
    private const val KEY_ACTOR_ID = "actor_id"
    private const val KEY_ACTOR_NAME = "actor_name"
    private const val KEY_ACTOR_EMAIL = "actor_email"
    private const val KEY_SERVER_URL = "server_url"
    private const val KEY_GOOGLE_LINK_PREFIX = "google_link_"

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun getToken(): String? = if (::prefs.isInitialized) prefs.getString(KEY_TOKEN, null) else null

    fun saveToken(token: String, actorId: String, name: String, email: String? = null) {
        if (!::prefs.isInitialized) return
        val editor = prefs.edit()
            .putString(KEY_TOKEN, token)
            .putString(KEY_ACTOR_ID, actorId)
            .putString(KEY_ACTOR_NAME, name)
        if (email != null) {
            editor.putString(KEY_ACTOR_EMAIL, email)
        }
        editor.apply()
    }

    fun getServerUrl(): String {
        val saved = if (::prefs.isInitialized) prefs.getString(KEY_SERVER_URL, null) else null
        return if (!saved.isNullOrBlank()) saved else com.sangam.app.BuildConfig.API_BASE_URL
    }

    fun saveServerUrl(url: String): Boolean {
        if (!::prefs.isInitialized) return false
        val clean = url.trim().trimEnd('/')
        val parsed = Uri.parse(clean)
        val scheme = parsed.scheme?.lowercase()
        if ((scheme != "http" && scheme != "https") || parsed.host.isNullOrBlank()) {
            return false
        }
        prefs.edit().putString(KEY_SERVER_URL, clean).apply()
        return true
    }

    /** Device-local password used only to link a Google account to the email/password API. */
    fun googleLinkSecret(email: String): String {
        if (!::prefs.isInitialized) return ""
        val key = KEY_GOOGLE_LINK_PREFIX + email.trim().lowercase()
        val existing = prefs.getString(key, null)
        if (!existing.isNullOrBlank()) return existing
        val bytes = ByteArray(32)
        SecureRandom().nextBytes(bytes)
        val secret = Base64.encodeToString(bytes, Base64.NO_WRAP or Base64.URL_SAFE)
        prefs.edit().putString(key, secret).apply()
        return secret
    }

    fun getActorEmail(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_EMAIL, null) else null

    fun clear() {
        if (!::prefs.isInitialized) return
        val server = prefs.getString(KEY_SERVER_URL, null)
        val links = prefs.all
            .filterKeys { it.startsWith(KEY_GOOGLE_LINK_PREFIX) }
            .mapNotNull { (key, value) -> (value as? String)?.let { key to it } }
        prefs.edit().clear().apply()
        if (server != null) saveServerUrl(server)
        if (links.isNotEmpty()) {
            val editor = prefs.edit()
            links.forEach { (key, value) -> editor.putString(key, value) }
            editor.apply()
        }
    }

    fun getActorId(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_ID, null) else null

    fun getActorName(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_NAME, null) else null

    fun isLoggedIn(): Boolean = getToken() != null
}
