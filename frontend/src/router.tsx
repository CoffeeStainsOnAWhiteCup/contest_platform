import { createBrowserRouter } from "react-router-dom";

import { RequireAuth, RequireRole } from "@/auth/guards";
import { AppShell } from "@/components/layout/AppShell";
import { CallbackPage } from "@/pages/CallbackPage";
import { ContestDetailPage } from "@/pages/ContestDetailPage";
import { ContestListPage } from "@/pages/ContestListPage";
import { GlobalRatingPage } from "@/pages/GlobalRatingPage";
import { HomePage } from "@/pages/HomePage";
import { LeaderboardPage } from "@/pages/LeaderboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProblemPage } from "@/pages/ProblemPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { SubmissionDetailPage } from "@/pages/SubmissionDetailPage";
import { SubmissionsPage } from "@/pages/SubmissionsPage";
import { AdminContestsPage } from "@/pages/admin/AdminContestsPage";
import { AdminTestsPage } from "@/pages/admin/AdminTestsPage";
import { AdminUsersPage } from "@/pages/admin/AdminUsersPage";
import { ContestFormPage } from "@/pages/admin/ContestFormPage";
import { ProblemFormPage } from "@/pages/admin/ProblemFormPage";
import { ProfilePage } from "@/pages/ProfilePage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "login", element: <LoginPage /> },
      { path: "register", element: <RegisterPage /> },
      { path: "auth/callback", element: <CallbackPage /> },
      { path: "contests", element: <ContestListPage /> },
      { path: "contests/:contestId", element: <ContestDetailPage /> },
      { path: "contests/:contestId/leaderboard", element: <LeaderboardPage /> },
      { path: "problems/:problemId", element: <ProblemPage /> },
      { path: "rating", element: <GlobalRatingPage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: "submissions", element: <SubmissionsPage /> },
          { path: "submissions/:submissionId", element: <SubmissionDetailPage /> },
          { path: "profile", element: <ProfilePage /> },
        ],
      },
      {
        element: <RequireRole roles={["admin"]} />,
        children: [
          { path: "admin/contests", element: <AdminContestsPage /> },
          { path: "admin/contests/new", element: <ContestFormPage /> },
          { path: "admin/contests/:contestId/edit", element: <ContestFormPage /> },
          { path: "admin/users", element: <AdminUsersPage /> },
        ],
      },
      {
        element: <RequireRole roles={["judge", "admin"]} />,
        children: [
          { path: "admin/contests/:contestId/problems/new", element: <ProblemFormPage /> },
          { path: "admin/problems/:problemId/edit", element: <ProblemFormPage /> },
          { path: "admin/problems/:problemId/tests", element: <AdminTestsPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
