package com.sangam.app.billing

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import com.revenuecat.purchases.CustomerInfo
import com.revenuecat.purchases.LogLevel
import com.revenuecat.purchases.ProductType
import com.revenuecat.purchases.PurchaseParams
import com.revenuecat.purchases.Purchases
import com.revenuecat.purchases.PurchasesConfiguration
import com.revenuecat.purchases.PurchasesError
import com.revenuecat.purchases.PurchasesErrorCode
import com.revenuecat.purchases.interfaces.GetStoreProductsCallback
import com.revenuecat.purchases.interfaces.LogInCallback
import com.revenuecat.purchases.interfaces.PurchaseCallback
import com.revenuecat.purchases.interfaces.ReceiveCustomerInfoCallback
import com.revenuecat.purchases.models.StoreProduct
import com.revenuecat.purchases.models.StoreTransaction
import com.sangam.app.BuildConfig
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Google Play Billing through RevenueCat.
 *
 * The app only starts a purchase. RevenueCat validates it with Google and
 * calls the backend webhook, which credits the wallet, so a modified client
 * cannot grant itself minutes. The buyer is identified to RevenueCat by their
 * Sangam actor id so the webhook knows whose wallet to credit.
 *
 * Play product ids (created by the owner in Play Console):
 *  - subscriptions `personal`, `vyapar`, `udyog`, `enterprise` (base plan `monthly`)
 *  - one-time `pilot` (7-day pilot) and consumable `topup_500`
 *
 * A build without REVENUECAT_ANDROID_KEY has billing switched off: plan
 * buttons explain that purchases are unavailable instead of crashing.
 */
object Billing {

    class BillingFailure(message: String, val userCancelled: Boolean = false) : Exception(message)

    const val PILOT_PRODUCT = "pilot"
    const val TOPUP_PRODUCT = "topup_500"
    private val SUBSCRIPTION_PLANS = setOf("personal", "vyapar", "udyog", "enterprise")

    val isEnabled: Boolean
        get() = BuildConfig.REVENUECAT_ANDROID_KEY.isNotBlank() && Purchases.isConfigured

    /** Call once from Application.onCreate. [actorId] is the signed-in user, if any. */
    fun configure(context: Context, actorId: String?) {
        val key = BuildConfig.REVENUECAT_ANDROID_KEY.trim()
        if (key.isEmpty() || Purchases.isConfigured) return
        if (BuildConfig.DEBUG) Purchases.logLevel = LogLevel.DEBUG
        Purchases.configure(
            PurchasesConfiguration.Builder(context.applicationContext, key)
                .appUserID(actorId?.takeIf { it.isNotBlank() })
                .build()
        )
    }

    /** Ties purchases to the signed-in Sangam actor. Safe to call repeatedly. */
    suspend fun logIn(actorId: String) {
        if (!isEnabled || actorId.isBlank()) return
        suspendCancellableCoroutine { cont ->
            Purchases.sharedInstance.logIn(actorId, object : LogInCallback {
                override fun onReceived(customerInfo: CustomerInfo, created: Boolean) = cont.resume(Unit)
                // Not fatal: the next purchase or app start retries.
                override fun onError(error: PurchasesError) = cont.resume(Unit)
            })
        }
    }

    fun logOut() {
        if (!isEnabled || Purchases.sharedInstance.isAnonymous) return
        Purchases.sharedInstance.logOut(object : ReceiveCustomerInfoCallback {
            override fun onReceived(customerInfo: CustomerInfo) {}
            override fun onError(error: PurchasesError) {}
        })
    }

    /** Store product for a Sangam plan id or one-time product id, with the Play price. */
    suspend fun product(productId: String): StoreProduct {
        requireEnabled()
        val type = if (productId in SUBSCRIPTION_PLANS) ProductType.SUBS else ProductType.INAPP
        val products = suspendCancellableCoroutine<List<StoreProduct>> { cont ->
            Purchases.sharedInstance.getProducts(listOf(productId), type, object : GetStoreProductsCallback {
                override fun onReceived(storeProducts: List<StoreProduct>) = cont.resume(storeProducts)
                override fun onError(error: PurchasesError) = cont.resumeWithException(failure(error, false))
            })
        }
        return products.firstOrNull()
            ?: throw BillingFailure("This plan is not on sale in Google Play yet. Please try again later.")
    }

    /** Opens the Play purchase sheet. Returns when Google confirms the payment. */
    suspend fun purchase(activity: Activity, productId: String): StoreTransaction {
        val product = product(productId)
        return suspendCancellableCoroutine { cont ->
            Purchases.sharedInstance.purchase(
                PurchaseParams.Builder(activity, product).build(),
                object : PurchaseCallback {
                    override fun onCompleted(storeTransaction: StoreTransaction, customerInfo: CustomerInfo) =
                        cont.resume(storeTransaction)

                    override fun onError(error: PurchasesError, userCancelled: Boolean) =
                        cont.resumeWithException(failure(error, userCancelled))
                },
            )
        }
    }

    suspend fun restore() {
        requireEnabled()
        suspendCancellableCoroutine { cont ->
            Purchases.sharedInstance.restorePurchases(object : ReceiveCustomerInfoCallback {
                override fun onReceived(customerInfo: CustomerInfo) = cont.resume(Unit)
                override fun onError(error: PurchasesError) = cont.resumeWithException(failure(error, false))
            })
        }
    }

    /** Play's own page where the user cancels or changes a subscription. */
    fun openManageSubscriptions(context: Context) {
        val uri = Uri.parse("https://play.google.com/store/account/subscriptions?package=${context.packageName}")
        context.startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    private fun requireEnabled() {
        if (!isEnabled) {
            throw BillingFailure("In-app purchases are not available in this build of the app.")
        }
    }

    private fun failure(error: PurchasesError, userCancelled: Boolean): BillingFailure {
        if (userCancelled || error.code == PurchasesErrorCode.PurchaseCancelledError) {
            return BillingFailure("Purchase cancelled. Nothing was charged.", userCancelled = true)
        }
        val message = when (error.code) {
            PurchasesErrorCode.NetworkError ->
                "No internet connection. Check your network and try again."
            PurchasesErrorCode.StoreProblemError ->
                "Google Play had a problem. Please try again in a few minutes."
            PurchasesErrorCode.PurchaseNotAllowedError ->
                "Purchases are not allowed on this device or Google account."
            PurchasesErrorCode.PurchaseInvalidError ->
                "Google Play could not process this purchase. Check your payment method in Play Store."
            PurchasesErrorCode.ProductNotAvailableForPurchaseError ->
                "This plan is not on sale in Google Play yet. Please try again later."
            PurchasesErrorCode.ProductAlreadyPurchasedError ->
                "You already own this plan. Tap Restore purchases if it is not showing."
            PurchasesErrorCode.PaymentPendingError ->
                "Payment is pending. Your plan activates as soon as Google confirms it."
            PurchasesErrorCode.ConfigurationError, PurchasesErrorCode.InvalidCredentialsError ->
                "In-app purchases are not set up correctly for this build. Please contact support."
            else -> error.message.ifBlank { "The purchase did not complete. Please try again." }
        }
        return BillingFailure(message)
    }
}
