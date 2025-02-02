#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug  5 12:45:22 2023

@author: stefano
"""

import numpy as np

b_params = np.array([8.40683102e-01, 0, 7.71445220e-04])
n_params = np.array([0., -0.79, 0.])
#n_params = np.array([0., -0.79, 0.])
theta_params = np.array([-6.48073315, 6.32545305, 0.8386719])
damping = np.array([0.2125, 0.2562])
#LIN_COV = np.diag([8.90797655e-07, 5.49874493e-07, 2.54163138e-04, 3.80228296e-04, 7.19007035e-02, 1.58019149e+00])
COL_COV = \
    0.01*np.array([[0., 0.,              0.,              0., 0.,              0.],
                [0., 0.,              0.,              0., 0.,              0.],
                [0., 0.,  2.09562546e-01,  3.46276805e-02, 0., -1.03489604e+00],
                [0., 0.,  3.46276805e-02,  9.41218351e-02, 0., -1.67029496e+00],
                [0., 0.,              0.,              0., 0.,              0.],
                [0., 0., -1.03489604e+00, -1.67029496e+00, 0.,  1.78037877e+02]])
sigma_1 = 1.27081569e-2
sigma_2 = 1.90114148e-2
sigma_3 = 79.0095745
LIN_COV = \
    np.array([[(sigma_1*0.02**3)/3,                  0., (sigma_1*0.02**2)/2,                  0.,                  0.,                   0.],
              [                 0., (sigma_2*0.02**3)/3,                  0., (sigma_2*0.02**2)/2,                  0.,                   0.],
              [(sigma_1*0.02**2)/2,                  0.,      2.54163138e-04,                   0,                  0.,                   0.],
              [                 0., (sigma_2*0.02**2)/2,                  0.,      3.80228296e-04,                  0.,                   0.],
              [                 0.,                  0.,                  0.,                  0., (sigma_3*0.02**3)/3,  (sigma_3*0.02**2)/2],
              [                 0.,                  0.,                  0.,                  0., (sigma_3*0.02**2)/2,       1.58019149e+00]])

OBS_COV = np.diag([5.0650402e-07, 8.3995428e-07, 1.6572967e-03])


class SystemModel:
    def __init__(self, env_info, agent_id):
        self.puck_radius = env_info['puck']['radius']
        self.mallet_radius = env_info['mallet']['radius']
        self.dt = env_info['dt']

        self.table = AirHockeyTable(env_info['table']['length'], env_info['table']['width'],
                                    env_info['table']['goal_width'], env_info['puck']['radius'],
                                    abs(env_info['robot']['base_frame'][agent_id - 1][0, 3]), env_info['dt'])
        self.F = np.eye(6)
        self.F_linear = np.eye(6)
        self.F_linear[0, 2] = self.F_linear[1, 3] = self.F_linear[4, 5] = self.dt
        self.F_linear[2, 2] = 1 - self.dt * damping[0]
        self.F_linear[3, 3] = 1 - self.dt * damping[1]
        self.Q_collision = np.zeros((6, 6))
        self.has_collision = False
        self.outside_boundary = False
        self.score = False

    def f(self, x):
        self.has_collision, self.outside_boundary, self.score, F, Q = self.table.check_collision(x)
        if self.has_collision:
            # Collision Dynamics
            self.F = F
            self.Q_collision = Q
        elif self.outside_boundary or self.score:
            # Stop Moving
            self.F = np.eye(6)
            self.Q_collision = np.zeros((6, 6))
        else:
            # Normal Prediction
            self.F = self.F_linear
        x = self.F @ x
        x[4] = (x[4] + np.pi) % (np.pi * 2) - np.pi
        return x


class AirHockeyTable:
    def __init__(self, length, width, goal_width, puck_radius, x_offset, dt):
        self.table_length = length
        self.table_width = width
        self.goal_width = goal_width
        self.puck_radius = puck_radius
        self.x_offset = x_offset
        self.dt = dt
        self.col_cov = COL_COV

        pos_offset = np.array([x_offset, 0])
        p1 = np.array([-length / 2 + puck_radius, -width / 2 + puck_radius]) + pos_offset
        p2 = np.array([length / 2 - puck_radius, -width / 2 + puck_radius]) + pos_offset
        p3 = np.array([length / 2 - puck_radius, width / 2 - puck_radius]) + pos_offset
        p4 = np.array([-length / 2 + puck_radius, width / 2 - puck_radius]) + pos_offset

        self.boundary = np.array([[p1, p2],
                                  [p2, p3],
                                  [p3, p4],
                                  [p4, p1]])

        self.local_rim_transform = np.zeros((4, 6, 6))
        self.local_rim_transform_inv = np.zeros((4, 6, 6))
        
        transform_tmp = np.eye(6)
        self.local_rim_transform[0] = transform_tmp.copy()
        self.local_rim_transform_inv[0] = transform_tmp.T.copy()

        transform_tmp = np.zeros((6, 6))
        transform_tmp[0, 1] = transform_tmp[2, 3] = transform_tmp[4, 4] = transform_tmp[5, 5] = 1
        transform_tmp[1, 0] = transform_tmp[3, 2] = -1
        self.local_rim_transform[1] = transform_tmp.copy()
        self.local_rim_transform_inv[1] = transform_tmp.T.copy()

        transform_tmp = np.eye(6)
        transform_tmp[0, 0] = transform_tmp[1, 1] = transform_tmp[2, 2] = transform_tmp[3, 3] = -1
        self.local_rim_transform[2] = transform_tmp.copy()
        self.local_rim_transform_inv[2] = transform_tmp.T.copy()

        transform_tmp = np.zeros((6, 6))
        transform_tmp[1, 0] = transform_tmp[3, 2] = transform_tmp[4, 4] = transform_tmp[5, 5] = 1
        transform_tmp[0, 1] = transform_tmp[2, 3] = -1
        self.local_rim_transform[3] = transform_tmp.copy()
        self.local_rim_transform_inv[3] = transform_tmp.T.copy()

        self._F_precollision = np.eye(6)
        self._F_postcollision = np.eye(6)
        self._jac_local_collision = np.eye(6)
        self._jac_local_collision[2, [2, 3, 5]] = b_params[0:3]
        self._jac_local_collision[3, [2, 3, 5]] = n_params[0:3]
        self._jac_local_collision[5, [2, 3, 5]] = theta_params[0:3]

    def check_collision(self, state):
        score = False
        outside_boundary = False
        collision = False

        u = state[2:4] * self.dt
        if np.abs(state[1]) < self.goal_width / 2:
            if state[0] + u[0] < -self.boundary[0, 0, 0] or state[0] + u[0] > self.boundary[0, 1, 0]:
                score = True
        elif np.any(state[:2] < self.boundary[0, 0]) or np.any(state[:2] > self.boundary[1, 1]):
            outside_boundary = True

        if not score and not outside_boundary:
            F, Q_collision, collision = self._check_collision_impl(state, u)

        else:
            F = np.eye(4)
            Q_collision = np.zeros((4, 6))
        return collision, outside_boundary, score, F, Q_collision

    def _cross_2d(self, u, v):
        return u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]

    def _check_collision_impl(self, state, u):
        F = np.eye(4)
        Q_collision = np.zeros((4, 6))
        v = self.boundary[:, 1] - self.boundary[:, 0]
        w = self.boundary[:, 0] - state[:2]
        denominator = self._cross_2d(v, u)
        s_col = self._cross_2d(v, w) / (denominator + 1e-6)
        r_col = self._cross_2d(u, w) / (denominator + 1e-6)
        collide_idx = np.where(np.logical_and(np.logical_and(1e-6 < s_col, s_col < 1 - 1e-6), np.logical_and(1e-6 < r_col, r_col < 1 - 1e-6)))[0]
        collision = False

        if len(collide_idx) > 0:
            collide_rim_idx = collide_idx[0]
            s_i = s_col[collide_rim_idx]
            self._F_precollision[0][2] = self._F_precollision[1][3] = self._F_precollision[4][5] = (s_i * self.dt)
            self._F_precollision[2][2] = 1 - s_i * self.dt * damping[0]
            self._F_precollision[3][3] = 1 - s_i*self.dt * damping[1]
            self._F_postcollision[0][2] = self._F_postcollision[1][3] = self._F_postcollision[4][5] = (1 - s_i) * self.dt
            self._F_postcollision[2][2] = 1 - (1 - s_i) * self.dt * damping[0]
            self._F_postcollision[3][3] = 1 - (1 - s_i)*self.dt * damping[1]
            Q_precollision = \
                np.array([[(sigma_1*(s_i*self.dt)**3)/3,                             0., (sigma_1*(s_i * self.dt)**2)/2,                             0.,                             0.,                             0.],
                          [                          0., (sigma_2*(s_i * self.dt)**3)/3,                             0., (sigma_2*(s_i * self.dt)**2)/2,                             0.,                             0.],
                          [(sigma_1*(s_i*self.dt)**2)/2,                             0.,        sigma_1*(s_i * self.dt),                              0,                             0.,                             0.],
                          [                          0., (sigma_2*(s_i * self.dt)**2)/2,                             0.,        sigma_2*(s_i * self.dt),                             0.,                             0.],
                          [                          0.,                             0.,                             0.,                             0., (sigma_3*(s_i*self.dt)**3)/3, (sigma_3*(s_i*self.dt)**2)/2],
                          [                          0.,                             0.,                             0.,                             0., (sigma_3*(s_i*self.dt)**2)/2,        sigma_3*(s_i*self.dt)]])
            Q_postcollision = \
                np.array([[(sigma_1*((1 -s_i)* self.dt)**3)/3,                                 0., (sigma_1*((1 -s_i)* self.dt)**2)/2,                                 0.,                                 0.,                                0.],
                          [                                0., (sigma_2*((1 -s_i)* self.dt)**3)/3,                                 0., (sigma_2*((1 -s_i)* self.dt)**2)/2,                                 0.,                                0.],
                          [(sigma_1*((1 -s_i)* self.dt)**2)/2,                                 0.,        sigma_1*((1 -s_i)* self.dt),                                  0,                                 0.,                                0.],
                          [                                0., (sigma_2*((1 -s_i)* self.dt)**2)/2,                                 0.,        sigma_2*((1 -s_i)* self.dt),                                 0.,                                0.],
                          [                                0.,                                 0.,                                 0.,                                 0., (sigma_3*((1 -s_i)* self.dt)**3)/3, (sigma_3*((1 -s_i)*self.dt)**2)/2],
                          [                                0.,                                 0.,                                 0.,                                 0., (sigma_3*((1 -s_i)* self.dt)**2)/2,        sigma_3*((1 -s_i)*self.dt)]])
            state_local = self.local_rim_transform[collide_rim_idx] @ state
            # Compute the slide direction
            slide_dir = 1 if state_local[2] + state_local[5] * self.puck_radius >= 0 else -1

            jac_local_collision = self._jac_local_collision.copy()
            jac_local_collision[2, 3] *= slide_dir
            jac_local_collision[5, 3] *= slide_dir

            F_collision = self.local_rim_transform_inv[collide_rim_idx] @ jac_local_collision @ self.local_rim_transform[collide_rim_idx]
            F = self._F_postcollision @ F_collision @ self._F_precollision
            Q_collision = (self._F_postcollision @ F_collision @ Q_precollision @ F_collision.T @ self._F_postcollision.T
                           + self._F_postcollision @ self.local_rim_transform_inv[collide_rim_idx] @ self.col_cov @ self.local_rim_transform_inv[collide_rim_idx].T @ self._F_postcollision.T 
                           + Q_postcollision)
            #Q_collision = self.local_rim_transform_inv[collide_rim_idx] @ self.col_cov @ self.local_rim_transform_inv[collide_rim_idx].T
            collision = True
        return F, Q_collision, collision


class PuckTracker:
    
    def __init__(self, env_info, agent_id=1):
        from scipy.stats.distributions import chi2
        
        self.system = SystemModel(env_info, agent_id)
        self.Q = LIN_COV

        self.R = OBS_COV
        self.H = np.zeros((3, 6))
        self.H[0, 0] = self.H[1, 1] = self.H[2, 4] = 1

        self.state = None
        self.P = None
        self.gate = chi2.ppf(0.9, df = 3)
        self.gamma = 1

    def reset(self, puck_pos):
        self.P = np.eye(6)
        self.state = np.zeros(6)
        self.state[[0, 1, 4]] = puck_pos

    def predict(self, state, P):
        predicted_state = self.system.f(state)
        if self.system.has_collision:
            Q = self.system.Q_collision
        elif self.system.outside_boundary or self.system.score:
            Q = self.system.Q_collision
        else:
            Q = self.Q
        P = self.system.F @ P @ self.system.F.T + Q
        return predicted_state, P

    def update(self, measurement, predicted_state, P):
        xy_innovation = measurement[:2] - predicted_state[:2]
        theta_innovation = (measurement[2] - predicted_state[4] + np.pi) % (np.pi * 2) - np.pi
        y = np.concatenate([xy_innovation, [theta_innovation]])
        
        #S_theory = self.H @ P @ self.H.T + self.R
        #numerator = np.trace(self.H @ P @ self.H.T)
        #denominator = np.trace(y @ y.T - self.R)
        if self.system.has_collision:#y.T @ np.linalg.inv(S_theory) @ y > self.gate: 
            self.gamma = 1#1#numerator/denominator
        #if numerator < denominator: 
        #    gamma = 1#numerator/denominator
        else:
            if self.gamma < 1: 
                self.gamma *= 1.1
                if self.gamma > 1:
                    self.gamma = 1
                
        #self.gamma = 1
        
        S = self.H @ P @ self.H.T / self.gamma + self.R
        K = P @ self.H.T @ np.linalg.inv(S) / self.gamma
        state = predicted_state + K @ y
        P = (np.eye(6) - K @ self.H) @ P / self.gamma
        return state, P

    def step(self, measurement):
        predicted_state, P = self.predict(self.state, self.P)
        # self.state = self.predicted_state
        self.state, self.P = self.update(measurement, predicted_state, P)

    def get_prediction(self, t, defend_line=0.):
        P_current = self.P.copy()
        state_current = self.state.copy()
        predict_time = 0

        for i in range(round(t / self.system.dt)):
            state_next, P_next = self.predict(state_current, P_current)
            if state_next[0] < defend_line:
                break
            if np.linalg.norm(state_current[2:4]) < 1e-2 and np.linalg.norm(state_next[2:4]) < 1e-2:
                predict_time = t
                break
            predict_time += self.system.dt
            state_current = state_next
            P_current = P_next
        print(predict_time)
        return state_current, P_current, predict_time


def puck_tracker_exp():
    from air_hockey_challenge.environments.planar.hit import AirHockeyHit
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    def set_puck_state(env, state, P, predict_time): 
        env._data.qvel[-3:] = np.zeros(3)
        env._data.joint("puck_record_x").qpos = state[0] - 1.51
        env._data.joint("puck_record_y").qpos = state[1]
        env._data.joint("puck_record_yaw").qpos = state[4]
        env._data.joint("puck_record_x").qvel = 0.
        env._data.joint("puck_record_y").qvel = 0.
        env._data.joint("puck_record_yaw").qvel = 0.

        eig_v, eig_vector = np.linalg.eig(P[:2, :2])
        if np.linalg.det(P[[0, 1]][:, [0, 1]]) > 1e-4:
            env._model.geom('puck_record').size[:2] = eig_v / np.max(eig_v) * 10 * 0.03165
            env._model.geom('puck_record').rgba = np.array([0., 0.2, 1., 0.6])
            env._model.geom('puck_record_ori').rgba = np.array([1., 0., 0., 1.])
        else:
            env._model.geom('puck_record').size[:2] = eig_v / 5e-4 * 0.03165
        env._data.joint('puck_record_yaw_vis').qpos = np.arctan2(eig_vector[1, 0], eig_vector[0, 0])

    env = AirHockeyHit()

    kalman_filter = PuckTracker(env.env_info, agent_id=1)
    predict_time = 0.5

    for epoch in range(1):
        # init_pos = np.random.uniform(kalman_filter.system.table.boundary[0, 1], kalman_filter.system.table.boundary[2, 1])
        # init_vel = np.random.randn(3)
        init_pos = np.array([0.6, -0.3])
        init_vel = np.array([-3, 3, 0.5])
        state = np.concatenate([init_pos, init_vel[:2], [0.5], init_vel[2:]])
        traj = []

        env.reset()
        env._data.joint("puck_x").qpos = state[0] - 1.51
        env._data.joint("puck_y").qpos = state[1]
        env._data.joint("puck_yaw").qpos = state[4]
        env._data.joint("puck_x").qvel = state[2]
        env._data.joint("puck_y").qvel = state[3]
        env._data.joint("puck_yaw").qvel = state[5]
        env._data.joint("planar_robot_1/joint_1").qpos = -np.pi / 2
        env._data.joint("planar_robot_1/joint_2").qpos = 0
        env._data.joint("planar_robot_1/joint_3").qpos = 0

        kalman_filter.reset(state[[0, 1, 4]])

        for i in range(200):
            obs, _, _, _ = env.step(np.array([0, 0., 0.]))
            meas = obs[:3] + np.random.multivariate_normal(np.zeros((3)), OBS_COV)
            kalman_filter.step(meas)
            state, P, _ = kalman_filter.get_prediction(predict_time)

            set_puck_state(env, state, P, predict_time)
            env.render()
            traj.append(np.concatenate([state.copy(), obs[:6]]))
        traj = np.array(traj)
        
        env.stop()

        fig = plt.figure(constrained_layout=True)
        gs = GridSpec(3, 4, figure=fig)
        ax2d = fig.add_subplot(gs[:, :2])
        ax2d.set_aspect(1)
        ax_x_pos = fig.add_subplot(gs[0, 2])
        ax_y_pos = fig.add_subplot(gs[1, 2])
        ax_theta_pos = fig.add_subplot(gs[2, 2])
        ax_x_vel = fig.add_subplot(gs[0, 3])
        ax_y_vel = fig.add_subplot(gs[1, 3])
        ax_theta_vel = fig.add_subplot(gs[2, 3])

        ax2d.plot(kalman_filter.system.table.boundary[0, :, 0], kalman_filter.system.table.boundary[0, :, 1], c='k',
                  lw=5)
        ax2d.plot(kalman_filter.system.table.boundary[1, :, 0], kalman_filter.system.table.boundary[1, :, 1], c='k',
                  lw=5)
        ax2d.plot(kalman_filter.system.table.boundary[2, :, 0], kalman_filter.system.table.boundary[2, :, 1], c='k',
                  lw=5)
        ax2d.plot(kalman_filter.system.table.boundary[3, :, 0], kalman_filter.system.table.boundary[3, :, 1], c='k',
                  lw=5)
        ax2d.scatter(traj[:, 0], traj[:, 1], s=2)
        ax2d.scatter(traj[:, 6], traj[:, 7], s=2)

        t = np.linspace(0, traj.shape[0] * env.env_info['dt'], traj.shape[0])
        t_predict = t + predict_time
        
        predict_step = int(predict_time/0.02)
        ax_x_pos.plot(t_predict[0:-predict_step], traj[:, 0][0:-predict_step])
        ax_y_pos.plot(t_predict[0:-predict_step], traj[:, 1][0:-predict_step])
        ax_theta_pos.plot(t_predict[0:-predict_step], traj[:, 4][0:-predict_step])

        ax_x_vel.plot(t_predict[0:-predict_step], traj[:, 2][0:-predict_step])
        ax_y_vel.plot(t_predict[0:-predict_step], traj[:, 3][0:-predict_step])
        ax_theta_vel.plot(t_predict[0:-predict_step], traj[:, 5][0:-predict_step])

        ax_x_pos.plot(t[predict_step:], traj[:, 6][predict_step:])
        ax_y_pos.plot(t[predict_step:], traj[:, 7][predict_step:])
        ax_theta_pos.plot(t[predict_step:], traj[:, 8][predict_step:])

        ax_x_vel.plot(t[predict_step:], traj[:, 9][predict_step:])
        ax_y_vel.plot(t[predict_step:], traj[:, 10][predict_step:])
        ax_theta_vel.plot(t[predict_step:], traj[:, 11][predict_step:])
        plt.show()


if __name__ == '__main__':  #if the script is run directly
    puck_tracker_exp()      #puck_tracker_exp() call
