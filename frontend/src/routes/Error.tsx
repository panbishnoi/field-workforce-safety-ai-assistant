// Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.]
// SPDX-License-Identifier: LicenseRef-.amazon.com.-AmznSL-1.0
// Licensed under the Amazon Software License  http://aws.amazon.com/asl/

import { getErrorMessage } from "@/lib/utils";
import { useRouteError } from "react-router-dom";

export default function Error() {
  const error = useRouteError();

  return (
    <main id="error-page">
      {/* i18n-disable */}
      <h3>Oops!</h3>
      <p>Sorry, an unexpected error has occurred.</p>
      {/* i18n-enable */}
      <code>
        <i>{getErrorMessage(error)}</i>
      </code>

      {/* i18n-disable */}
      <footer>Industrial AI Demo</footer>
      {/* i18n-enable */}
    </main>
  );
}
