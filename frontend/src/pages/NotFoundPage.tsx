import React from 'react';
import { Link } from 'react-router-dom';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="text-center py-16 space-y-4">
      <h2 className="text-3xl font-bold text-slate-800">404 - Page Not Found</h2>
      <p className="text-slate-500 text-sm">The requested page does not exist.</p>
      <div>
        <Link
          to="/"
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-sky-600 hover:bg-sky-700"
        >
          Return Home
        </Link>
      </div>
    </div>
  );
};

