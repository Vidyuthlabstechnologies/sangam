package com.sangam.app.network

import android.content.Context
import android.content.SharedPreferences

object TokenManager {
    private const val PREFS_NAME = "sangam_prefs"
    private const val KEY_TOKEN = "jwt_token"
    private const val KEY_ACTOR_ID = "actor_id"
    private const val KEY_ACTOR_NAME = "actor_name"
    private const val KEY_ACTOR_EMAIL = "actor_email"
    private const val KEY_SERVER_URL = "server_url"

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

    fun saveServerUrl(url: String) {
        if (::prefs.isInitialized) {
            val clean = url.trim().trimEnd('/')
            prefs.edit().putString(KEY_SERVER_URL, clean).apply()
        }
    }

    fun getActorEmail(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_EMAIL, null) else null

    fun clear() {
        if (::prefs.isInitialized) {
            val server = prefs.getString(KEY_SERVER_URL, null)
            prefs.edit().clear().apply()
            if (server != null) {
                saveServerUrl(server)
            }
        }
    }

    fun getActorId(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_ID, null) else null

    fun getActorName(): String? = if (::prefs.isInitialized) prefs.getString(KEY_ACTOR_NAME, null) else null

    fun isLoggedIn(): Boolean = getToken() != null
}
