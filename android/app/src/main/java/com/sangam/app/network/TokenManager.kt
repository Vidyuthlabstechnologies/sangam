package com.sangam.app.network

import android.content.Context
import android.content.SharedPreferences

object TokenManager {
    private const val PREFS_NAME = "sangam_prefs"
    private const val KEY_TOKEN = "jwt_token"
    private const val KEY_ACTOR_ID = "actor_id"
    private const val KEY_ACTOR_NAME = "actor_name"

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun getToken(): String? = prefs.getString(KEY_TOKEN, null)

    fun saveToken(token: String, actorId: String, name: String) {
        prefs.edit()
            .putString(KEY_TOKEN, token)
            .putString(KEY_ACTOR_ID, actorId)
            .putString(KEY_ACTOR_NAME, name)
            .apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    fun getActorId(): String? = prefs.getString(KEY_ACTOR_ID, null)

    fun getActorName(): String? = prefs.getString(KEY_ACTOR_NAME, null)

    fun isLoggedIn(): Boolean = getToken() != null
}
