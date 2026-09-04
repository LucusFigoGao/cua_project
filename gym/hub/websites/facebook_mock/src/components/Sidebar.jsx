import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Users, Bookmark, Calendar, Clock, ChevronDown, ChevronUp, Flag, Users2, Store, Video } from 'lucide-react';
import { useApp } from '../store/AppContext';

const Sidebar = () => {
  const { currentUser, state } = useApp();
  const navigate = useNavigate();
  const [showMore, setShowMore] = useState(false);

  const SidebarItem = ({ icon: Icon, text, color = "text-blue-500", src, path }) => (
    <div
      className="flex items-center gap-3 p-2 hover:bg-gray-200 rounded-lg cursor-pointer transition-colors"
      onClick={() => path && navigate(path)}
    >
      {src ? (
        <img src={src} alt="" className="w-9 h-9 rounded-full object-cover" />
      ) : (
        <Icon size={36} className={`${color}`} />
      )}
      <span className="font-medium text-[15px]">{text}</span>
    </div>
  );

  return (
    <div className="hidden lg:block w-[360px] h-screen fixed left-0 top-14 pt-4 px-2 overflow-y-auto hover:overflow-y-scroll scrollbar-thin pb-20">
      <Link to="/profile">
        <SidebarItem src={currentUser.avatar} text={currentUser.name} />
      </Link>
      <SidebarItem icon={Users} text="Friends" src="https://static.xx.fbcdn.net/rsrc.php/v3/y8/r/S0U5ECzYUSu.png" path="/friends" />
      <SidebarItem icon={Users2} text="Groups" src="https://static.xx.fbcdn.net/rsrc.php/v3/y5/r/PrjLkDYpYbH.png" path="/groups" />
      <SidebarItem icon={Store} text="Marketplace" src="https://static.xx.fbcdn.net/rsrc.php/v3/yz/r/kEcCUNzHTab.png" path="/marketplace" />
      <SidebarItem icon={Flag} text="Pages" src="https://static.xx.fbcdn.net/rsrc.php/v3/y9/r/DHBHg965q3d.png" path={state.pages && state.pages.length > 0 ? `/pages/${state.pages[0].id}` : '/'} />
      <SidebarItem icon={Calendar} text="Events" src="https://static.xx.fbcdn.net/rsrc.php/v3/yv/r/QAyfjudAqqG.png" path="/events" />
      <SidebarItem icon={Clock} text="Memories" src="https://static.xx.fbcdn.net/rsrc.php/v3/y8/r/he-BkogidIc.png" path="/saved" />
      <SidebarItem icon={Bookmark} text="Saved" src="https://static.xx.fbcdn.net/rsrc.php/v3/yD/r/lVijPkTeN-r.png" path="/saved" />

      {showMore && (
        <>
          <SidebarItem icon={Video} text="Watch" src="https://static.xx.fbcdn.net/rsrc.php/v3/y6/r/u43U3TBNiwH.png" path="/watch" />
        </>
      )}

      <div
        className="flex items-center gap-3 p-2 hover:bg-gray-200 rounded-lg cursor-pointer transition-colors"
        onClick={() => setShowMore(v => !v)}
      >
        <div className="w-9 h-9 bg-gray-300 rounded-full flex items-center justify-center">
          {showMore ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </div>
        <span className="font-medium text-[15px]">{showMore ? 'See less' : 'See more'}</span>
      </div>

      <div className="border-t border-gray-300 my-2 mx-2"></div>

      <div className="px-2">
        <h3 className="text-gray-500 font-semibold text-[17px] mb-2">Your Shortcuts</h3>
        <SidebarItem src="https://picsum.photos/50/50?random=g1" text="React Developers" path="/groups" />
        {(state.pages || []).map(page => (
          <SidebarItem key={page.id} src={page.avatar} text={page.name} path={`/pages/${page.id}`} />
        ))}
      </div>

      <div className="px-4 mt-auto text-xs text-gray-500 leading-relaxed">
        Privacy  · Terms  · Advertising  · Ad Choices   · Cookies  · More · Meta © 2026
      </div>
    </div>
  );
};

export default Sidebar;
