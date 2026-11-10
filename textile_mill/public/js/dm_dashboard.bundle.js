import { DMDashboard } from "./dm_dashboard/dashboard";

frappe.provide("textile_mill");

textile_mill.DMDashboard = DMDashboard;

textile_mill.mount_dashboard = function (wrapper, dashboard) {
	if (wrapper.dm_dashboard) {
		wrapper.dm_dashboard.on_show();
		return;
	}
	wrapper.dm_dashboard = new DMDashboard(wrapper, dashboard);
};
