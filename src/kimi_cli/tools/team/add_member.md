Add a member to an existing team.

Each member has an agent type and a role within the team. Roles determine which phases of orchestrated tasks the member participates in.

Parameters:
- team_name (string, required): The name of the team to add the member to.
- agent_type (string, required): The subagent type for this member (e.g. 'explore', 'code', 'test').
- role (string, optional): The role of the member. One of: 'leader', 'worker', 'reviewer', 'explorer'. Defaults to 'worker'.
