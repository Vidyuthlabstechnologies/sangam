package com.sangam.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.sangam.app.ui.screens.*

object Routes {
    const val LOGIN = "login"
    const val DASHBOARD = "dashboard"
    const val ONBOARDING_WIZARD = "onboarding_wizard"
    const val CALL_INBOX = "call_inbox"
    const val WORKFLOWS = "workflows"
    const val WORKFLOW_DETAIL = "workflows/{workflowId}"
    const val APPROVALS = "approvals"
    const val ACTORS = "actors"
    const val AI_ASSISTANT = "ai_assistant"
    const val VOICE_WORKFLOW = "voice_workflow"
    const val PAYMENT = "payment/{workflowId}/{workflowName}"
    const val VENDORS = "vendors"
    const val VENDOR_ADD = "vendors/add"
    const val VENDOR_DETAIL = "vendors/{vendorId}"

    fun workflowDetail(id: String) = "workflows/$id"
    fun vendorDetail(id: String) = "vendors/$id"
    fun payment(workflowId: String, workflowName: String) = "payment/$workflowId/$workflowName"
}

@Composable
fun SangamNavHost(
    navController: NavHostController,
    startDestination: String,
) {
    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoginSuccess = { isNewUser ->
                    // Dashboard is always the root, so Back from onboarding lands there.
                    navController.navigate(Routes.DASHBOARD) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                    if (isNewUser) {
                        navController.navigate(Routes.ONBOARDING_WIZARD)
                    }
                },
            )
        }
        composable(Routes.DASHBOARD) {
            DashboardScreen(
                onNavigateToOnboarding = { navController.navigate(Routes.ONBOARDING_WIZARD) },
                onNavigateToCallInbox = { navController.navigate(Routes.CALL_INBOX) },
                onNavigateToWorkflows = { navController.navigate(Routes.WORKFLOWS) },
                onNavigateToApprovals = { navController.navigate(Routes.APPROVALS) },
                onNavigateToActors = { navController.navigate(Routes.ACTORS) },
                onNavigateToAIAssistant = { navController.navigate(Routes.AI_ASSISTANT) },
                onNavigateToVoiceWorkflow = { navController.navigate(Routes.VOICE_WORKFLOW) },
                onNavigateToVendors = { navController.navigate(Routes.VENDORS) },
                onOpenWorkflow = { id -> navController.navigate(Routes.workflowDetail(id)) },
                onSignOut = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.ONBOARDING_WIZARD) {
            OnboardingWizardScreen(
                onBack = { navController.popBackStack() },
                onOpenCallInbox = { navController.navigate(Routes.CALL_INBOX) },
            )
        }
        composable(Routes.CALL_INBOX) {
            CallInboxScreen(
                onBack = { navController.popBackStack() },
            )
        }
        composable(Routes.VENDORS) {
            VendorListScreen(
                onVendorClick = { id -> navController.navigate(Routes.vendorDetail(id)) },
                onAddVendor = { navController.navigate(Routes.VENDOR_ADD) },
            )
        }
        composable(Routes.VENDOR_ADD) {
            val ctx = androidx.compose.ui.platform.LocalContext.current
            AddVendorScreen(
                onDone = { id ->
                    navController.navigate(Routes.vendorDetail(id)) {
                        popUpTo(Routes.VENDORS)
                    }
                },
                onBack = { navController.popBackStack() },
                // Bundled synthetic licence stands in for the camera so the
                // flow is demonstrable on an emulator with no camera.
                sampleLicenceBytes = {
                    ctx.assets.open("sample_cdsco_licence.pdf").use { it.readBytes() }
                },
            )
        }
        composable(
            route = Routes.VENDOR_DETAIL,
            arguments = listOf(navArgument("vendorId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val vendorId = backStackEntry.arguments?.getString("vendorId") ?: return@composable
            VendorDetailScreen(
                vendorId = vendorId,
                onBack = { navController.popBackStack() },
                onQualificationSubmitted = { },
            )
        }
        composable(Routes.WORKFLOWS) {
            WorkflowListScreen(
                onWorkflowClick = { id -> navController.navigate(Routes.workflowDetail(id)) },
                onVoiceCreate = { navController.navigate(Routes.VOICE_WORKFLOW) },
            )
        }
        composable(
            route = Routes.WORKFLOW_DETAIL,
            arguments = listOf(navArgument("workflowId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val workflowId = backStackEntry.arguments?.getString("workflowId") ?: return@composable
            WorkflowDetailScreen(
                workflowId = workflowId,
                onBack = { navController.popBackStack() },
                onPay = { wfId, wfName ->
                    navController.navigate(Routes.payment(wfId, wfName))
                },
            )
        }
        composable(Routes.APPROVALS) {
            ApprovalsScreen(
                onWorkflowClick = { id -> navController.navigate(Routes.workflowDetail(id)) },
            )
        }
        composable(Routes.ACTORS) {
            ActorsScreen()
        }
        composable(Routes.AI_ASSISTANT) {
            AIAssistantScreen(
                onBack = { navController.popBackStack() },
            )
        }
        composable(Routes.VOICE_WORKFLOW) {
            VoiceWorkflowScreen(
                onBack = { navController.popBackStack() },
                onWorkflowCreated = {
                    navController.navigate(Routes.WORKFLOWS) {
                        popUpTo(Routes.DASHBOARD)
                    }
                },
            )
        }
        composable(
            route = Routes.PAYMENT,
            arguments = listOf(
                navArgument("workflowId") { type = NavType.StringType },
                navArgument("workflowName") { type = NavType.StringType },
            ),
        ) { backStackEntry ->
            val workflowId = backStackEntry.arguments?.getString("workflowId") ?: return@composable
            val workflowName = backStackEntry.arguments?.getString("workflowName") ?: "Workflow"
            PaymentScreen(
                workflowId = workflowId,
                workflowName = workflowName,
                onBack = { navController.popBackStack() },
            )
        }
    }
}
