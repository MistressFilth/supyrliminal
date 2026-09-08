Feature: Suppression scanner
  The PG plugin emits PG201-PG205 to audit every PG/PYD suppression.

  Scenario: Blanket noqa fires PG201
    Given a Python file with a blanket `# noqa`:
      """
      x = 1  # noqa
      """
    When the file is scanned
    Then PG201 fires on line 1

  Scenario: Broad noqa fires PG202
    Given a Python file with three PG/PYD codes in one noqa:
      """
      x = 1  # noqa: PG001, PG002, PG003
      """
    When the file is scanned
    Then PG202 fires on line 1

  Scenario: Unauthorized noqa fires PG203
    Given a Python file with an unauthorized noqa:
      """
      def parse():
          return 1  # noqa: PG001
      """
    And an empty registry
    When the file is scanned
    Then PG203 fires on line 2

  Scenario: Authorized noqa does not fire PG203
    Given a Python file with an unauthorized noqa:
      """
      def parse():
          return 1  # noqa: PG001
      """
    And a registry entry authorizing "legacy.parse" / "PG001"
    When the file is scanned
    Then PG203 does not fire

  Scenario: Project settings disable PG fires PG205
    Given a pyproject.toml with:
      """
      [tool.flake8]
      extend-ignore = "PG001, E501"
      """
    When the file is scanned
    Then PG205 fires for PG001
    And PG205 does not fire for E501
