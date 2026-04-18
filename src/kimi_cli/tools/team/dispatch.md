Dispatch a task to team members using a specified strategy.

Parameters:
- team_name (string, required): The name of the team to dispatch the task to.
- task (string, required): The task description to dispatch.
- strategy (string, optional): Dispatch strategy. One of: 'leader' (send to leader only), 'broadcast' (send to all members), 'round_robin' (send to next available worker). Defaults to 'leader'.
