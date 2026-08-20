// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { LucideIcon } from "lucide-react";

type Props = {
  /**
   * @deprecated 设计稿 4a 去掉了图标井：设置纸里靠发丝线分节，不再每项配一个图标。
   * 保留这个 prop 只是为了不改动十几个调用点，它不再渲染任何东西。
   */
  icon?: LucideIcon;
  title: string;
  desc?: string;
  children?: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
};

/**
 * 设置纸里的一节。
 *
 * 原来每一节是一张 `.hd-setting-card`——纸上再放卡＝双层容器，而且六张等重的卡
 * 排成一列，字体/主题/语言各占一整张只为装一个分段控件（设计稿 4a 的诊断）。
 * 现在它是纸上的一行：上边一道发丝线分节，没有卡底、没有边框投影、没有图标井。
 */
export function Section({ title, desc, children, className, action }: Props) {
  return (
    <section className={`kq-set-row ${className ?? ""}`}>
      <div className="kq-set-row-head">
        <div className="kq-set-row-copy">
          <h2>{title}</h2>
          {desc && <p>{desc}</p>}
        </div>
        {action && <div className="kq-set-row-action">{action}</div>}
      </div>
      {children && <div className="kq-set-row-body">{children}</div>}
    </section>
  );
}
