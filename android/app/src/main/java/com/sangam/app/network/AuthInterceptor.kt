package com.sangam.app.network

import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

/** Adds the signed-in user's Firebase ID token to every API request. */
class AuthInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = currentBearerToken()
        val request = if (token != null) {
            original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            original
        }
        return chain.proceed(request)
    }

    companion object {
        fun currentBearerToken(): String? =
            FirebaseSession.idTokenBlocking() ?: ZitadelAuth.accessTokenForRequest()
    }
}

/**
 * On a 401, force one Firebase token refresh and retry. Covers a token that
 * expired between the cache check and the server, or a revoked session.
 */
class TokenRefreshAuthenticator : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.priorResponse != null) return null // already retried once
        if (!FirebaseSession.isSignedIn()) return null
        val fresh = FirebaseSession.idTokenBlocking(forceRefresh = true) ?: return null
        val sent = response.request.header("Authorization")
        if (sent == "Bearer $fresh") return null // same token; refreshing will not help
        return response.request.newBuilder()
            .header("Authorization", "Bearer $fresh")
            .build()
    }
}
