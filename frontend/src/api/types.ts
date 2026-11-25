import type { components } from "./schema";

type Schemas = components["schemas"];

export type TokenResponse = Schemas["TokenResponse"];
export type UserRead = Schemas["UserRead"];
export type Profile = Schemas["Profile"];
export type AdminView = Schemas["AdminView"];
export type UserRole = Schemas["UserRole"];

export type ContestStatus = Schemas["ContestStatus"];
export type ContestPhase = ContestStatus | "scheduled";
export type ContestRead = Schemas["ContestRead"];
export type ContestDetail = Schemas["ContestDetail"];
export type ContestListResponse = Schemas["ContestListResponse"];
export type ContestCreate = Schemas["ContestCreate"];
export type ContestUpdate = Schemas["ContestUpdate"];

export type ProblemSummary = Schemas["ProblemSummary"];
export type ProblemDetail = Schemas["ProblemDetail"];
export type ProblemCreate = Schemas["ProblemCreate"];
export type ProblemUpdate = Schemas["ProblemUpdate"];
export type TestRead = Schemas["TestRead"];
export type TestCreate = Schemas["TestCreate"];
export type TestUpdate = Schemas["TestUpdate"];

export type Language = Schemas["Language"];
export type SubmissionStatus = Schemas["SubmissionStatus"];
export type VerdictStatus = Schemas["VerdictStatus"];
export type SubmissionCreate = Schemas["SubmissionCreate"];
export type SubmissionRead = Schemas["SubmissionRead"];
export type SubmissionDetail = Schemas["SubmissionDetail"];
export type SubmissionListResponse = Schemas["SubmissionListResponse"];
export type VerdictRead = Schemas["VerdictRead"];
export type SubmissionTestResultRead = Schemas["SubmissionTestResultRead"];
export type RejudgeResponse = Schemas["RejudgeResponse"];

export type Board = Schemas["Board"];
export type Entry = Schemas["Entry"];
export type TelegramLinkStatus = Schemas["LinkStatus"];
export type TelegramLink = Schemas["Link"];

export type Page = {
  page: number;
  size: number;
};
