import { expect, it } from "vitest";

import { ApiError, errorMessage } from "./errors";

it.each([
  [403, "Account blocked", "Аккаунт заблокирован."],
  [409, "Email is already registered", "Этот email уже зарегистрирован."],
])("translates the public message while preserving the API code %s", (status, detail, label) => {
  const error = new ApiError(detail, status, detail);
  expect(errorMessage(error)).toBe(label);
  expect(error.code).toBe(detail);
});
