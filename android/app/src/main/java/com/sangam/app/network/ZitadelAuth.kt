package com.sangam.app.network

import android.app.Activity
import android.content.Intent
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import com.sangam.app.BuildConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.suspendCancellableCoroutine
import net.openid.appauth.AuthState
import net.openid.appauth.AuthorizationException
import net.openid.appauth.AuthorizationRequest
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.AuthorizationService
import net.openid.appauth.AuthorizationServiceConfiguration
import net.openid.appauth.ResponseTypeValues
import kotlin.coroutines.resume

/**
 * Authorization code + PKCE in the system browser (Custom Tabs).
 * The organization id is whatever Zitadel puts in the access token.
 * Intents and the APK do not carry a client secret or an org id Sangam would trust.
 */
object ZitadelAuth {
    private const val REDIRECT_URI = "com.sangam.app:/oauth2callback"

    val loggedIn = MutableStateFlow(false)
    val error = MutableStateFlow<String?>(null)

    var launchRequest: ((Intent) -> Unit)? = null

    fun start(activity: Activity) {
        val issuer = BuildConfig.ZITADEL_ISSUER
        val clientId = BuildConfig.ZITADEL_CLIENT_ID
        if (issuer.isBlank() || clientId.isBlank()) {
            error.value = "Set ZITADEL_ISSUER and ZITADEL_CLIENT_ID to the self-hosted Zitadel instance."
            return
        }
        error.value = null
        AuthorizationServiceConfiguration.fetchFromIssuer(Uri.parse(issuer)) { config, ex ->
            if (config == null) {
                error.value = ex?.errorDescription ?: "Could not reach the Zitadel issuer"
                return@fetchFromIssuer
            }
            val request = AuthorizationRequest.Builder(
                config,
                clientId,
                ResponseTypeValues.CODE,
                Uri.parse(REDIRECT_URI),
            )
                .setScopes(
                    "openid",
                    "profile",
                    "email",
                    "offline_access",
                    "urn:zitadel:iam:user:resourceowner",
                )
                .build()
            val service = AuthorizationService(activity)
            val customTabs = CustomTabsIntent.Builder().setShowTitle(true).build()
            val intent = service.getAuthorizationRequestIntent(request, customTabs)
            service.dispose()
            launchRequest?.invoke(intent) ?: run {
                error.value = "Sign-in is not ready"
            }
        }
    }

    fun handleAuthorizationResult(data: Intent?) {
        if (data == null) return
        val response = AuthorizationResponse.fromIntent(data)
        val exception = AuthorizationException.fromIntent(data)
        if (response == null) {
            error.value = exception?.errorDescription ?: "Sign-in was cancelled"
            return
        }
        val service = AuthorizationService(TokenManager.appContext())
        val authState = AuthState(response, exception)
        service.performTokenRequest(response.createTokenExchangeRequest()) { tokenResponse, tokenException ->
            service.dispose()
            if (tokenResponse == null) {
                error.value = tokenException?.errorDescription ?: "Token exchange failed"
                return@performTokenRequest
            }
            authState.update(tokenResponse, tokenException)
            TokenManager.saveAuthState(authState.jsonSerializeString())
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val me = ApiClient.authApi.me()
                    TokenManager.saveProfile(me.actor_id, me.name)
                    RealtimeClient.start()
                    loggedIn.value = true
                } catch (e: Exception) {
                    TokenManager.clear()
                    error.value = e.message ?: "Could not link the Sangam profile"
                }
            }
        }
    }

    /**
     * Access token for API calls. Refresh goes through AppAuth's token endpoint,
     * which is Zitadel's, using the stored refresh token and the PKCE client.
     */
    fun accessTokenForRequest(): String? {
        val raw = TokenManager.readAuthStateJson() ?: return TokenManager.getToken()
        val state = try {
            AuthState.jsonDeserialize(raw)
        } catch (_: Exception) {
            return null
        }
        val expiry = state.accessTokenExpirationTime
        val stillFresh = expiry == null || expiry > System.currentTimeMillis() + 30_000
        if (stillFresh || state.refreshToken == null) return state.accessToken
        val service = AuthorizationService(TokenManager.appContext())
        return try {
            runBlocking {
                suspendCancellableCoroutine { cont ->
                    state.performActionWithFreshTokens(service) { accessToken, _, ex ->
                        if (!cont.isActive) return@performActionWithFreshTokens
                        if (ex != null || accessToken == null) {
                            cont.resume(state.accessToken)
                        } else {
                            TokenManager.saveAuthState(state.jsonSerializeString())
                            cont.resume(accessToken)
                        }
                    }
                }
            }
        } catch (_: Exception) {
            state.accessToken
        } finally {
            service.dispose()
        }
    }
}
