import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const navCls = ({ isActive }: { isActive: boolean }) =>
  `fd-nav__link${isActive ? " fd-nav__link--active" : ""}`;

export function SidebarNavLink({
  to,
  end,
  label,
  icon,
}: {
  to: string;
  end?: boolean;
  label: string;
  icon: ReactNode;
}) {
  return (
    <NavLink to={to} end={end} className={navCls} title={label}>
      <span className="fd-nav__glyph" aria-hidden="true">
        {icon}
      </span>
      <span className="fd-nav__label">{label}</span>
    </NavLink>
  );
}
