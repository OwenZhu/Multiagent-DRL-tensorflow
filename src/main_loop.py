"""Main loop module"""

import argparse
import json
import os

import numpy as np

from cpr_game import CPRGame
from agent import Agent
import helper


def main():
    parser = argparse.ArgumentParser()
    parsed_args = helper.build_argument_parser(parser)
    with open('config/config.json', 'r') as f:
        conf = json.load(f)

    MODEL_NAME = parsed_args.model
    N_AGENT = parsed_args.n_agent
    W = conf["game"]["sustainable_weight"] = \
        parsed_args.sustainable_weight
    LEARN_MODE = parsed_args.learn_mode
    CURRENT_VERSION = parsed_args.version

    if MODEL_NAME not in conf["model"]:
        raise NotImplementedError

    env_conf = conf["env"]
    SAVE_RESULT_PATH = os.path.join(
        env_conf["log_path"],
        "{}_model".format(MODEL_NAME),
        CURRENT_VERSION,
        "{}_{}".format(W, N_AGENT)
    )
    SAVE_MODEL_PATH = os.path.join(
        SAVE_RESULT_PATH,
        "checkpoints"
    )

    # Init game environment
    game = CPRGame(conf["game"])
    states = np.zeros((N_AGENT, env_conf["state_space"]))
    next_states = np.zeros((N_AGENT, env_conf["state_space"]))
    rewards = np.zeros(N_AGENT)

    # -------------- train mode --------------

    if LEARN_MODE == "train":
        # Init agents
        agents = [
            Agent(
                "agent_{}".format(i),
                conf["model"][MODEL_NAME],
            )
            for i in range(N_AGENT)
        ]

        avg_scores = []
        epsilon = env_conf["init_epsilon"]
        epoch = 0
        while epsilon >= env_conf["min_epsilon"]:
            # Reset Game Environment
            game.reset()
            efforts = np.array([env_conf["total_init_effort"] / N_AGENT] * N_AGENT)
            score = 0.0
            for _ in range(env_conf["max_train_round"]):
                for i, agent in enumerate(agents):

                    if MODEL_NAME == "DDPG":
                        action = agent.act(
                            states[i],
                            epsilon=epsilon,
                            upper_bound=game.pool / N_AGENT
                        )
                    elif MODEL_NAME == "DQN":
                        action = agent.act(
                            states[i],
                            epsilon=epsilon,
                            pre_action=effort_list[i]
                        )

                    efforts[i] = action
                    agent.remember(
                        states[i],
                        action,
                        rewards[i],
                        next_states[i]
                    )

                next_states, rewards, done = game.step(efforts)
                score += sum(rewards) / N_AGENT
                if done:
                    break

            [agent.learn() for agent in agents]

            print("epoch: {}, score: {}, e: {:.2}"
                  .format(epoch, score, epsilon))
            epsilon -= env_conf["epsilon_decay"]
            epoch += 1
            avg_scores.append(score)

        [agent.close(SAVE_MODEL_PATH) for agent in agents]
        helper.save_result(
            {"train_avg_score.txt": avg_scores},
            SAVE_RESULT_PATH
        )

    # -------------- test mode --------------

    elif LEARN_MODE == "test":
        # Init agents
        agent_list = [
            Agent(
                "agent_{}".format(i),
                conf["model"][MODEL_NAME],
                SAVE_MODEL_PATH
            )
            for i in range(N_AGENT)
        ]

        avg_asset_seq = [0]
        pool_level_seq = []
        avg_score_seq = []

        for t in range(env_conf["max_test_round"]):
            pool_level_seq.append(game.pool)
            effort_list = [env_conf["total_init_effort"] / N_AGENT] * N_AGENT
            for i, agent in enumerate(agent_list):
                if MODEL_NAME == "DDPG":
                    action = agent.act(
                        states[i],
                        upper_bound=game.pool / N_AGENT
                    )
                elif MODEL_NAME == "DQN":
                    action = agent.act(
                        states[i],
                        pre_action=effort_list[i]
                    )

                effort_list[i] = action
                agent.remember(
                    states[i],
                    action,
                    rewards[i],
                    next_states[i]
                )
                effort_list[i] = action

            next_states, rewards, done = game.step(effort_list)

            avg_score_seq.append(sum(rewards) / N_AGENT)
            avg_asset_seq.append(
                avg_asset_seq[-1] + next_states[0][3] / N_AGENT)

            if done:
                break

        for agent in agent_list:
            agent.close()

        helper.save_result(
            {
                "test_avg_score.txt": avg_asset_seq,
                "test_assets.txt": avg_asset_seq,
                "test_resource_level.txt": pool_level_seq
            },
            SAVE_RESULT_PATH
        )


if __name__ == "__main__":
    main()
