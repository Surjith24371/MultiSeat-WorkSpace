/**
 * mockData.js
 * Default seed resources, hourly slots, and mock user personas.
 */

export const MOCK_RESOURCES = [
    { id: 'res_1', name: 'Apex Boardroom', type: 'room', capacity: 16, icon: '🏢' },
    { id: 'res_2', name: 'Zenith Conference', type: 'room', capacity: 8, icon: '👥' },
    { id: 'res_3', name: 'Nexus Meeting Room', type: 'room', capacity: 6, icon: '🤝' },
    { id: 'res_4', name: 'Vortex Huddle Space', type: 'room', capacity: 4, icon: '💬' },
    { id: 'res_5', name: 'Workstation Pod 101', type: 'pod', capacity: 1, icon: '💻' },
    { id: 'res_6', name: 'Workstation Pod 102', type: 'pod', capacity: 1, icon: '💻' },
    { id: 'res_7', name: 'Workstation Pod 103', type: 'pod', capacity: 1, icon: '💻' },
    { id: 'res_8', name: 'Workstation Pod 104', type: 'pod', capacity: 1, icon: '💻' },
    { id: 'res_9', name: 'GPU Cluster Alpha (A100)', type: 'cluster', capacity: 4, icon: '⚡' },
    { id: 'res_10', name: 'GPU Cluster Beta (H100)', type: 'cluster', capacity: 4, icon: '⚡' },
    { id: 'res_11', name: 'Compute Node 01', type: 'cluster', capacity: 2, icon: '🖥️' },
    { id: 'res_12', name: 'Compute Node 02', type: 'cluster', capacity: 2, icon: '🖥️' },
];

export const MOCK_TIME_SLOTS = [
    '09:00',
    '10:00',
    '11:00',
    '12:00',
    '13:00',
    '14:00',
    '15:00',
    '16:00'
];

export const MOCK_USERS = [
    {
        id: 'user_alice',
        name: 'Alice Walker',
        email: 'alice@workspace.io',
        role: 'AI Researcher',
        avatar: '👩‍💼'
    },
    {
        id: 'user_bob',
        name: 'Bob Martinez',
        email: 'bob@workspace.io',
        role: 'DevOps Lead',
        avatar: '👨‍💻'
    },
    {
        id: 'user_charlie',
        name: 'Charlie Chen',
        email: 'charlie@workspace.io',
        role: 'Product Architect',
        avatar: '🧑‍🚀'
    }
];
