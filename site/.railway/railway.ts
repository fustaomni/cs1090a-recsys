// The site's Railway project as code (A.98), imported with `railway config pull` from the live
// service and replacing site/railway.json, which Railway stops reading on 2026-12-01.
//
// WHAT railway.json SAID, AND WHERE IT WENT:
//   builder RAILPACK      -> build.builder below, stated explicitly.
//   restart ON_FAILURE    -> deliberately NOT declared. It is Railway's default, which Railway
//                            stores as null, so declaring it is a diff no apply can ever close
//                            (railwayapp/cli issue 1184). Leaving it unset is the faithful form.
// Variables are unmanaged (project policy below): the site is a static build with no
// application variables, so none are in git and no apply can delete one.
import { defineRailway, project, service } from "railway/iac";

export default defineRailway(() => {
  const cs1090aRecsysSite = service("cs1090a-recsys-site", {
    build: { buildEnvironment: "V3", builder: "RAILPACK" },
    replicas: { "us-west2": 1 },
    domains: ["cs1090a.fustaomni.com"],
  });

  return project("cs1090a-recsys-site", {
    variables: { managed: false },
    resources: [cs1090aRecsysSite],
  });
});
