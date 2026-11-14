package com.sangam.app.ui

import android.content.Context
import com.sangam.app.network.TokenManager
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest

/**
 * Serves realistic sample data so screenshots show filled screens, not just error states.
 * Points the app at it through TokenManager's saved server URL.
 */
object FakeBackend {
    private var server: MockWebServer? = null

    fun start(context: Context) {
        if (server != null) return
        val s = MockWebServer()
        s.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = route(request.method.orEmpty(), path) ?: return MockResponse().setResponseCode(404)
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }
        s.start()
        server = s
        // TokenManager normally uses EncryptedSharedPreferences, which needs the Android keystore.
        val prefs = context.getSharedPreferences("screenshot_prefs", Context.MODE_PRIVATE)
        TokenManager::class.java.getDeclaredField("prefs").apply { isAccessible = true }.set(TokenManager, prefs)
        TokenManager.saveServerUrl(s.url("/").toString())
    }

    private const val WF1 = """{"id":"wf1","name":"Approve site visit for Ramesh Traders","description":"Caller asked for a factory visit on Monday","initiator_id":"a1","current_phase":"APPROVAL","state":"active","phases":["INITIATION","APPROVAL","EXECUTION"],"created_at":"2026-11-14T10:00:00Z","updated_at":"2026-11-14T10:00:00Z","approvals":[{"id":"ap1","workflow_id":"wf1","status":"pending","required_actors":["a1"]}]}"""
    private const val WF2 = """{"id":"wf2","name":"Send quotation for 20 tonnes of quartz powder","description":null,"initiator_id":"a1","current_phase":"EXECUTION","state":"draft","phases":["INITIATION","EXECUTION"],"created_at":"2026-11-13T10:00:00Z","updated_at":"2026-11-13T10:00:00Z","approvals":[],"handoffs":[],"exceptions":[]}"""
    private const val WF3 = """{"id":"wf3","name":"Follow up on missed call from Dr. Priya's clinic","description":null,"initiator_id":"a1","current_phase":"SETTLEMENT","state":"completed","phases":["INITIATION","SETTLEMENT"],"created_at":"2026-11-12T10:00:00Z","updated_at":"2026-11-12T10:00:00Z","approvals":[],"handoffs":[],"exceptions":[]}"""

    private fun route(method: String, path: String): String? = when {
        path == "/workflows" -> """{"items":[$WF1,$WF2,$WF3],"total":3,"page":1,"page_size":10}"""
        path.startsWith("/workflows/") -> WF1
        path == "/actors" -> """[
            {"id":"a1","type":"human","name":"Varshini","email":"owner@example.in","roles":["owner"],"is_active":true},
            {"id":"a2","type":"ai_agent","name":"Kite reception agent","email":null,"roles":["agent"],"is_active":true},
            {"id":"a3","type":"human","name":"Suresh (accounts)","email":"accounts@example.in","roles":["approver"],"is_active":false}]"""
        path == "/vendors" -> """[
            {"id":"v1","name":"Sri Lakshmi Pharma Distributors","legal_name":null,"gstin":"29ABCDE1234F1Z5","address":"Bengaluru","status":"qualified","created_at":"2026-11-01T00:00:00Z","qualification_workflow_id":null,
             "licences":[{"id":"l1","licence_type":"Form 20B","licence_number":"KA-B12-345","issuing_authority":"Drugs Control, Karnataka","issue_date":"2022-01-01","expiry_date":"2026-12-01","verified":true,"extraction_confidence":0.97,"is_expired":false,"days_until_expiry":17}],"has_expired_licence":false,"is_qualifiable":true},
            {"id":"v2","name":"Mahalaxmi Medicals","legal_name":null,"gstin":null,"address":null,"status":"draft","created_at":"2026-11-02T00:00:00Z","qualification_workflow_id":null,"licences":[],"has_expired_licence":false,"is_qualifiable":false}]"""
        path.startsWith("/vendors/") -> """{"id":"v1","name":"Sri Lakshmi Pharma Distributors","legal_name":"Sri Lakshmi Pharma Distributors Pvt Ltd","gstin":"29ABCDE1234F1Z5","address":"12 Chickpet, Bengaluru 560053","status":"qualified","created_at":"2026-11-01T00:00:00Z","qualification_workflow_id":null,
             "licences":[{"id":"l1","licence_type":"Form 20B","licence_number":"KA-B12-345","issuing_authority":"Drugs Control, Karnataka","issue_date":"2022-01-01","expiry_date":"2026-12-01","verified":true,"extraction_confidence":0.97,"is_expired":false,"days_until_expiry":17}],"has_expired_licence":false,"is_qualifiable":true}"""
        path == "/onboarding/wallet/me" -> """{"call_balance_inr":1240.5,"deployment_status":"ACTIVE","referral_code":"KITE42","assigned_did":"+918041234567","business_name":"Ramesh Traders","primary_language":"kn-IN"}"""
        path == "/onboarding/plans" -> null
        path == "/agent-callbacks" -> """[
            {"id":"c1","caller_name":"Anil Kumar","caller_phone":"+919845012345","service":"Quartz powder quote","language":"Kannada","urgency":"urgent","notes":"Needs 20 tonnes delivered to Hosur by Friday. Asked for best price per tonne.","preferred_time":"Today 4-6 PM","status":"new"},
            {"id":"c2","caller_name":"Fatima Begum","caller_phone":"+919900112233","service":"Appointment","language":"Hindi","urgency":"normal","notes":"Wants a Saturday morning slot for her son.","preferred_time":"","status":"contacted"}]"""
        path == "/voice-agents/agents" -> """[{"id":"va1","tenant_id":"t1","app_id":"app1","app_version":3,"label":"Reception (Kannada)","agent_phone_number":"+918041234567","can_call_out":true},
            {"id":"va2","tenant_id":"t1","app_id":"app2","app_version":1,"label":"Sales follow-up","agent_phone_number":null,"can_call_out":false}]"""
        path == "/voice-agents/calls" -> """[{"id":"call1","attempt_id":"at1","app_id":"app1","user_phone":"+919845012345","status":"completed","duration_seconds":143.0,"failure_reason":null,"created_at":"2026-11-14T09:30:00Z"},
            {"id":"call2","attempt_id":"at2","app_id":"app1","user_phone":"+919900112233","status":"failed","duration_seconds":null,"failure_reason":"No answer","created_at":"2026-11-14T08:10:00Z"}]"""
        else -> null
    }
}
