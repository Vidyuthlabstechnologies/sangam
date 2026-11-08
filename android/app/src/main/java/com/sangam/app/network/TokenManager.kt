package com.sangam.app.network

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object TokenManager {
    private const val PREFS_NAME = "sangam_secure_prefs"
    private const val LEGACY_PREFS = "sangam_prefs"
    private const val KEY_TOKEN = "jwt_token"
    private const val KEY_AUTH_STATE = "zitadel_auth_state"
    private const val KEY_ACTOR_ID = "actor_id"
    private const val KEY_ACTOR_NAME = "actor_name"
    private const val KEY_ACTOR_EMAIL = "actor_email"
    private const val KEY_SERVER_URL = "server_url"
    // Written by builds before Firebase sign-in. Removed on startup.
    private const val KEY_GOOGLE_LINK_PREFIX = "google_link_"

    private lateinit var prefs: SharedPreferences
    private lateinit var appContext: Context

    fun init(context: Context) {
        appContext = context.applicationContext
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        prefs = EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
        // One-time move off the old plaintext file, then wipe it.
        val legacy = context.getSharedPreferences(LEGACY_PREFS, Context.MODE_PRIVATE)
        val legacyToken = legacy.getString(KEY_TOKEN, null)
        if (!legacyToken.isNullOrEmpty() && prefs.getString(KEY_TOKEN, null).isNullOrEmpty()) {
            prefs.edit()
                .putString(KEY_TOKEN, legacyToken)
                .putString(KEY_ACTOR_ID, legacy.getString(KEY_ACTOR_ID, null))
                .putString(KEY_ACTOR_NAME, legacy.getString(KEY_ACTOR_NAME, null))
                .apply()
        }
        val legacyServer = legacy.getString(KEY_SERVER_URL, null)
        if (!legacyServer.isNullOrEmpty() && prefs.getString(KEY_SERVER_URL, null).isNullOrEmpty()) {
            prefs.edit().putString(KEY_SERVER_URL, legacyServer).apply()
        }
        legacy.edit().clear().apply()
        // Older builds linked Google accounts with a random device password.
        // Firebase replaces that, so the secrets are dropped.
        val staleLinks = prefs.all.keys.filter { it.startsWith(KEY_GOOGLE_LINK_PREFIX) }
        if (staleLinks.isNotEmpty()) {
            val editor = prefs.edit()
            staleLinks.forEach { editor.remove(it) }
            editor.apply()
        }
    }

    fun appContext(): Context = appContext

    fun readAuthStateJson(): String? = prefs.getString(KEY_AUTH_STATE, null)

    fun saveAuthState(json: String) {
        prefs.edit()
            .putString(KEY_AUTH_STATE, json)
            .remove(KEY_TOKEN)
            .apply()
    }

    fun saveProfile(actorId: String, name: String, email: String? = null) {
        val editor = prefs.edit()
            .putString(KEY_ACTOR_ID, actorId)
            .putString(KEY_ACTOR_NAME, name)
        if (email != null) {
            editor.putString(KEY_ACTOR_EMAIL, email)
        }
        editor.apply()
    }

    fun saveToken(token: String, actorId: String, name: String, email: String? = null) {
        if (!::prefs.isInitialized) return
        val editor = prefs.edit()
            .putString(KEY_TOKEN, token)
            .putString(KEY_ACTOR_ID, actorId)
            .putString(KEY_ACTOR_NAME, name)
            .remove(KEY_AUTH_STATE)
        if (email != null) {
            editor.putString(KEY_ACTOR_EMAIL, email)
        }
        editor.apply()
    }

    fun getToken(): String? {
        if (!::prefs.isInitialized) return null
        val raw = prefs.getString(KEY_AUTH_STATE, null)
        if (!raw.isNullOrEmpty()) {
            return try {
                net.openid.appauth.AuthState.jsonDeserialize(raw).accessToken
            } catch (_: Exception) {
                null
            }
        }
        return prefs.getString(KEY_TOKEN, null)
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

    fun getActorEmail(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_EMAIL, null) else null

    fun clear() {
        if (!::prefs.isInitialized) return
        val server = prefs.getString(KEY_SERVER_URL, null)
        prefs.edit().clear().apply()
        if (server != null) saveServerUrl(server)
    }

    fun getActorId(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_ID, null) else null

    fun getActorName(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_NAME, null) else null

    /** Signed in through Firebase (Google or email), or a legacy stored token. */
    fun isLoggedIn(): Boolean = FirebaseSession.isSignedIn() || getToken() != null
}
