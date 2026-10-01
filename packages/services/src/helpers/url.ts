/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Ensures an API request URL has a trailing slash on its path component, preserving
 * the query string and hash. Required by the Django backend's `APPEND_SLASH` behavior
 * — under Kubernetes ingress, requests without a trailing slash can fail instead of
 * 301-redirecting. Intended to be applied by an axios request interceptor so callers
 * do not need to remember to add the slash.
 *
 * Examples:
 *   "/api/foo"             -> "/api/foo/"
 *   "/api/foo/"            -> "/api/foo/"
 *   "/api/foo?x=1"         -> "/api/foo/?x=1"
 *   "/api/foo#frag"        -> "/api/foo/#frag"
 *   "https://h/api/foo"    -> "https://h/api/foo/"
 *   "" | "/"               -> unchanged
 */
export function ensureAPITrailingSlash(url: string): string {
  if (!url) return url;
  const boundary = url.search(/[?#]/);
  const path = boundary === -1 ? url : url.slice(0, boundary);
  const suffix = boundary === -1 ? "" : url.slice(boundary);
  if (!path || path.endsWith("/")) return url;
  return `${path}/${suffix}`;
}

/**
 * Same as `ensureAPITrailingSlash`, but skips absolute URLs whose origin is not this
 * instance's Django `baseURL`. Signed S3/GCS upload URLs go through `APIService` with
 * an empty `baseURL`; slashing them invalidates the signature and 403s the upload.
 */
export function normalizeAPIRequestURL(url: string, baseURL: string): string {
  if (isForeignAbsoluteURL(url, baseURL)) return url;
  return ensureAPITrailingSlash(url);
}

function isForeignAbsoluteURL(url: string, baseURL: string): boolean {
  try {
    const requestUrl = new URL(url);
    if (!baseURL) return true;
    try {
      return requestUrl.origin !== new URL(baseURL).origin;
    } catch {
      return true;
    }
  } catch {
    return false;
  }
}

/**
 * Where to send the browser when an API call returns 401, for an app served under
 * `basePath` (e.g. "/plane" when the web app is not at the domain root). `next_path` is
 * kept router-relative (without the base path) because the router adds the basename.
 * Returns null on the entry page itself: it runs its own current-user request on mount,
 * and bouncing "/" to "/?next_path=/" would reload it in a loop.
 *
 * Examples (basePath "/plane"):
 *   "/plane/ws/projects/" -> "/plane/?next_path=%2Fws%2Fprojects%2F"
 *   "/plane/" | "/plane"  -> null
 * Examples (basePath ""):
 *   "/ws/projects/"       -> "/?next_path=%2Fws%2Fprojects%2F"
 */
export function unauthorizedRedirectURL(pathname: string, basePath: string): string | null {
  const base = basePath.replace(/\/+$/, "");
  const inBase = base && (pathname === base || pathname.startsWith(`${base}/`));
  const routePath = inBase ? pathname.slice(base.length) || "/" : pathname;
  if (routePath === "/") return null;
  return `${base}/?next_path=${encodeURIComponent(routePath)}`;
}
