package com.sangam.app.network

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object TokenManager {
    private const val PREFS_NAME = "sangam_secure_prefs"
    private const val LEGACY_PREFS = "sangam_prefs"
    private const val KEY_TOKEN = "jwt_token"
    private const val KEY_ACTOR_ID = "actor_id"
    private const val KEY_ACTOR_NAME = "actor_name"

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
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
        legacy.edit().clear().apply()
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
